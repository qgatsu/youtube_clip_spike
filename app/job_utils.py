from __future__ import annotations

from typing import Dict
from urllib.parse import urlencode, urlparse, urlunparse


def format_result(url: str, data: Dict) -> Dict:
    sorted_spikes = sorted(
        data["spikes"], key=lambda spike: spike.get("peak_value", 0), reverse=True
    )
    return {
        "series": data["series"],
        "spikes": [
            {
                **spike,
                "jump_url": build_jump_url(url, spike["start_time"]),
            }
            for spike in sorted_spikes
        ],
    }


def build_jump_url(url: str, timestamp_seconds: float) -> str:
    parsed = urlparse(url)
    query = parsed.query
    params = dict()
    if query:
        for chunk in query.split("&"):
            if "=" in chunk:
                key, value = chunk.split("=", 1)
                params[key] = value
    params["t"] = f"{int(timestamp_seconds)}s"
    new_query = urlencode(params)
    return urlunparse(parsed._replace(query=new_query))
