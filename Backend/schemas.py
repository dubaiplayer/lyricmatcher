from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecommendRequest(BaseModel):
    song: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)

    @field_validator("song", "artist", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class QueryInfo(BaseModel):
    song: str
    artist: str


class RecommendationItem(BaseModel):
    rank: int
    artist: str
    song: str
    score: float


class TrackMediaRequestItem(BaseModel):
    song: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)

    @field_validator("song", "artist", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class TrackMediaRequest(BaseModel):
    tracks: list[TrackMediaRequestItem] = Field(..., min_length=1, max_length=20)


class TrackMediaItem(BaseModel):
    song: str
    artist: str
    youtube: str
    cover: str


class TrackMediaResponse(BaseModel):
    tracks: list[TrackMediaItem]


class RecommendSuccessResponse(BaseModel):
    success: Literal[True] = True
    query: QueryInfo
    recommendations: list[RecommendationItem]


class RecommendFailureResponse(BaseModel):
    success: Literal[False] = False
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
