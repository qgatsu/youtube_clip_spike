from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests


_VIDEO_ID_RE = re.compile(r"[0-9A-Za-z_-]{6,}")


def extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    if _VIDEO_ID_RE.fullmatch(url):
        return url

    parsed = urlparse(url)

    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/")
        return candidate or None

    if "youtube.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        if "v" in query:
            return query["v"][0]

        match = re.match(r"^/embed/([0-9A-Za-z_-]{6,})", parsed.path)
        if match:
            return match.group(1)

    return None


@lru_cache(maxsize=128)
def fetch_video_duration_seconds(video_id: str, api_key: str | None) -> Optional[int]:
    if not api_key or not video_id:
        return None
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": api_key,
        "part": "contentDetails",
        "id": video_id,
    }
    resp = requests.get(url, params=params, timeout=float(os.getenv("YOUTUBE_API_TIMEOUT", 10)))
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items") or []
    if not items:
        return None
    duration_iso = items[0].get("contentDetails", {}).get("duration")
    return _parse_iso8601_duration(duration_iso)


def _parse_iso8601_duration(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    pattern = re.compile(
        r"^PT"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?$"
    )
    match = pattern.match(value)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds
