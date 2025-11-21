from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_app_config(config_path: Path | None = None) -> Dict[str, Any]:
    load_dotenv(BASE_DIR / ".env")
    path = config_path or DEFAULT_CONFIG_PATH
    file_config = load_yaml_config(path)

    return {
        "CHATDOWNLOADER": {
            "request_timeout": int(
                os.getenv(
                    "CHATDOWNLOADER_REQUEST_TIMEOUT",
                    file_config.get("chatdownloader", {}).get("request_timeout", 10),
                )
            ),
            "message_limit": file_config.get("chatdownloader", {}).get("message_limit"),
        },
        "YOUTUBE": {
            "api_key": os.getenv(
                "YOUTUBE_API_KEY", file_config.get("youtube", {}).get("api_key")
            ),
            "segment_duration_seconds": int(
                os.getenv(
                    "YOUTUBE_SEGMENT_DURATION_SECONDS",
                    file_config.get("youtube", {}).get("segment_duration_seconds", 900),
                )
            ),
            "parallel_segments": int(
                os.getenv(
                    "YOUTUBE_PARALLEL_SEGMENTS",
                    file_config.get("youtube", {}).get("parallel_segments", 1),
                )
            ),
        },
        "CPS": {
            "bucket_size_seconds": float(
                os.getenv(
                    "CPS_BUCKET_SIZE_SECONDS",
                    file_config.get("cps", {}).get("bucket_size_seconds", 5),
                )
            ),
            "smoothing_window_seconds": float(
                os.getenv(
                    "CPS_SMOOTHING_WINDOW_SECONDS",
                    file_config.get("cps", {}).get("smoothing_window_seconds", 30),
                )
            ),
            "smoothing_average_window": int(
                os.getenv(
                    "CPS_SMOOTHING_AVERAGE_WINDOW",
                    file_config.get("cps", {}).get("smoothing_average_window", 6),
                )
            ),
        },
        "SPIKE_DETECTION": {
            "min_prominence": float(
                os.getenv(
                    "SPIKE_MIN_PROMINENCE",
                    file_config.get("spike_detection", {}).get("min_prominence", 2.0),
                )
            ),
            "min_gap_seconds": float(
                os.getenv(
                    "SPIKE_MIN_GAP_SECONDS",
                    file_config.get("spike_detection", {}).get("min_gap_seconds", 10),
                )
            ),
            "pre_start_buffer_seconds": float(
                os.getenv(
                    "SPIKE_PRE_START_BUFFER_SECONDS",
                    file_config.get("spike_detection", {}).get(
                        "pre_start_buffer_seconds", 10
                    ),
                )
            ),
        },
        "REDIS": {
            "url": os.getenv(
                "REDIS_URL",
                file_config.get("redis", {}).get("url", "redis://localhost:6379/0"),
            ),
            "queue_name": os.getenv(
                "REDIS_QUEUE_NAME", file_config.get("redis", {}).get("queue_name", "analysis")
            ),
            "job_timeout": int(
                os.getenv(
                    "REDIS_JOB_TIMEOUT",
                    file_config.get("redis", {}).get("job_timeout", 900),
                )
            ),
            "result_ttl": int(
                os.getenv(
                    "REDIS_RESULT_TTL",
                    file_config.get("redis", {}).get("result_ttl", 86400),
                )
            ),
        },
    }
