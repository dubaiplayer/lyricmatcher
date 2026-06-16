import hashlib
import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_BACKEND_DIR, "recommender_cache")
_TRACK_CACHE_PATH = os.path.join(_CACHE_DIR, "youtube_track_cache.json")
_LEGACY_URL_CACHE_PATH = os.path.join(_CACHE_DIR, "youtube_urls.json")

logger = logging.getLogger(__name__)
_track_cache: dict[str, dict[str, str]] | None = None
_cache_lock = threading.Lock()

YOUTUBE_API_KEY = (os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
DEFAULT_COVER = (
    "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=600&q=80"
)


@dataclass(frozen=True)
class TrackMedia:
    youtube: str
    cover: str


def _cache_key(song: str, artist: str) -> str:
    return hashlib.md5(f"{song.strip().lower()}\0{artist.strip().lower()}".encode("utf-8")).hexdigest()


def _search_query(song: str, artist: str) -> str:
    return f"{artist} {song} official audio".strip()


def youtube_fallback_url(song: str, artist: str) -> str:
    query = f"{song} {artist}".strip()
    return f"https://www.youtube.com/embed?listType=search&list={urllib.parse.quote(query)}&autoplay=1"


def _best_thumbnail_url(thumbnails: dict[str, Any]) -> str:
    for size in ("maxres", "high", "medium", "default"):
        url = thumbnails.get(size, {}).get("url")
        if url:
            return str(url)
    return ""


def _lookup_via_youtube_api(song: str, artist: str) -> TrackMedia | None:
    if not YOUTUBE_API_KEY:
        return None

    query = _search_query(song, artist)
    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "videoCategoryId": "10",
            "key": YOUTUBE_API_KEY,
        }
    )
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        logger.warning("YouTube Data API lookup failed for %r", query, exc_info=True)
        return None

    items = payload.get("items") or []
    if not items:
        return None

    video_id = items[0].get("id", {}).get("videoId")
    snippet = items[0].get("snippet", {})
    thumbnails = snippet.get("thumbnails", {})
    cover = _best_thumbnail_url(thumbnails) or DEFAULT_COVER
    if not video_id:
        return None

    return TrackMedia(
        youtube=f"https://www.youtube.com/watch?v={video_id}&autoplay=1",
        cover=cover,
    )


def _lookup_via_youtube_search(song: str, artist: str) -> TrackMedia:
    query = _search_query(song, artist)
    youtube = youtube_fallback_url(song, artist)
    cover = DEFAULT_COVER

    try:
        from youtube_search import YoutubeSearch

        results = YoutubeSearch(query, max_results=1).to_dict()
        if results:
            first = results[0]
            video_id = first.get("id")
            thumbs = first.get("thumbnails") or []
            if video_id:
                youtube = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
            if thumbs:
                cover = str(thumbs[0])
    except Exception:
        logger.warning("YouTube search lookup failed for %r", query, exc_info=True)

    return TrackMedia(youtube=youtube, cover=cover)


def _load_track_cache() -> dict[str, dict[str, str]]:
    global _track_cache
    if _track_cache is not None:
        return _track_cache

    _track_cache = {}
    if os.path.exists(_TRACK_CACHE_PATH):
        try:
            with open(_TRACK_CACHE_PATH, "r", encoding="utf-8") as fp:
                raw = json.load(fp)
            if isinstance(raw, dict):
                _track_cache = {
                    key: value
                    for key, value in raw.items()
                    if isinstance(value, dict) and value.get("youtube")
                }
        except Exception:
            _track_cache = {}

    if not _track_cache and os.path.exists(_LEGACY_URL_CACHE_PATH):
        try:
            with open(_LEGACY_URL_CACHE_PATH, "r", encoding="utf-8") as fp:
                legacy = json.load(fp)
            if isinstance(legacy, dict):
                for key, youtube in legacy.items():
                    if isinstance(youtube, str):
                        _track_cache[key] = {"youtube": youtube, "cover": DEFAULT_COVER}
        except Exception:
            pass

    return _track_cache


def _save_track_cache() -> None:
    if _track_cache is None:
        return
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_TRACK_CACHE_PATH, "w", encoding="utf-8") as fp:
        json.dump(_track_cache, fp)


def resolve_track_media(song: str, artist: str) -> TrackMedia:
    key = _cache_key(song, artist)
    with _cache_lock:
        cache = _load_track_cache()
        cached = cache.get(key)
        if cached and cached.get("youtube") and cached.get("cover"):
            return TrackMedia(youtube=cached["youtube"], cover=cached["cover"])

    media = _lookup_via_youtube_api(song, artist) or _lookup_via_youtube_search(song, artist)

    with _cache_lock:
        cache = _load_track_cache()
        cache[key] = {"youtube": media.youtube, "cover": media.cover}
        _save_track_cache()

    return media


def resolve_track_media_parallel(
    tracks: list[tuple[str, str]],
    *,
    max_workers: int = 5,
) -> list[TrackMedia]:
    if not tracks:
        return []

    cache = _load_track_cache()
    keys = [_cache_key(song, artist) for song, artist in tracks]
    results: list[TrackMedia | None] = [None] * len(tracks)
    pending: dict[int, tuple[str, str]] = {}

    for index, (song, artist) in enumerate(tracks):
        cached = cache.get(keys[index])
        if cached and cached.get("youtube") and cached.get("cover"):
            results[index] = TrackMedia(youtube=cached["youtube"], cover=cached["cover"])
        else:
            pending[index] = (song, artist)

    if pending:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(pending))) as executor:
            future_map = {
                executor.submit(resolve_track_media, song, artist): index
                for index, (song, artist) in pending.items()
            }
            for future in as_completed(future_map):
                index = future_map[future]
                song, artist = pending[index]
                try:
                    results[index] = future.result()
                except Exception:
                    results[index] = TrackMedia(
                        youtube=youtube_fallback_url(song, artist),
                        cover=DEFAULT_COVER,
                    )

    return [
        result
        if result is not None
        else TrackMedia(
            youtube=youtube_fallback_url(tracks[i][0], tracks[i][1]),
            cover=DEFAULT_COVER,
        )
        for i, result in enumerate(results)
    ]


def resolve_youtube_urls_parallel(
    tracks: list[tuple[str, str]],
    *,
    max_workers: int = 5,
) -> list[str]:
    return [media.youtube for media in resolve_track_media_parallel(tracks, max_workers=max_workers)]
