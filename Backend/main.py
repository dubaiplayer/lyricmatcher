import logging
import os
import sys
from typing import Union

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager

from lyricsrecommender import recommend, search, warm_dataset_cache
from youtube_resolver import resolve_track_media_parallel
from schemas import (
    HealthResponse,
    QueryInfo,
    RecommendFailureResponse,
    RecommendRequest,
    RecommendSuccessResponse,
    RecommendationItem,
    TrackMediaRequest,
    TrackMediaResponse,
    TrackMediaItem,
)

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    warm_dataset_cache(verbose=True)
    yield


app = FastAPI(title="Recommendr API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=RecommendFailureResponse(
            message="Invalid request. Provide both song and artist.",
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=RecommendFailureResponse(
            message="An internal error occurred while generating recommendations.",
        ).model_dump(),
    )


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse()


@app.post(
    "/api/recommend",
    response_model=Union[RecommendSuccessResponse, RecommendFailureResponse],
)
def recommend_songs(body: RecommendRequest) -> RecommendSuccessResponse | RecommendFailureResponse:
    song = body.song
    artist = body.artist

    if not song or not artist:
        return RecommendFailureResponse(message="Song and artist are required.")

    df, row_id = search(song, artist, verbose=False)
    if df is None or row_id is None:
        return RecommendFailureResponse(message="Song not found")

    raw_recommendations = recommend(df, row_id, verbose=False)
    if not raw_recommendations:
        return RecommendFailureResponse(message="Could not generate recommendations")

    matched = df.iloc[row_id]

    return RecommendSuccessResponse(
        query=QueryInfo(song=str(matched["song"]), artist=str(matched["artist"])),
        recommendations=[
            RecommendationItem(
                rank=item["rank"],
                artist=item["artist"],
                song=item["song"],
                score=item["score"],
            )
            for item in raw_recommendations
        ],
    )


@app.post("/api/track-media", response_model=TrackMediaResponse)
def track_media(body: TrackMediaRequest) -> TrackMediaResponse:
    tracks = [(item.song, item.artist) for item in body.tracks]
    media = resolve_track_media_parallel(tracks)
    return TrackMediaResponse(
        tracks=[
            TrackMediaItem(
                song=song,
                artist=artist,
                youtube=entry.youtube,
                cover=entry.cover,
            )
            for (song, artist), entry in zip(tracks, media)
        ]
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
