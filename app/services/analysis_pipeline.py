from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .chat_loader import ChatLoader, ChatMessage
from .cps_analyzer import CPSAnalyzer
from .spike_detector import SpikeDetector
from .youtube_api import extract_video_id, fetch_video_duration_seconds

ProgressCallback = Callable[[int, Optional[float]], None]


def fetch_chat_messages(
    url: str,
    chat_config: Dict,
    youtube_config: Optional[Dict] = None,
    progress_callback: Optional[ProgressCallback] = None,
    chunk_size: int = 1000,
) -> List[ChatMessage]:
    youtube_config = youtube_config or {}
    if _can_parallel_fetch(youtube_config):
        result = _fetch_parallel_messages(
            url=url,
            chat_config=chat_config,
            youtube_config=youtube_config,
            progress_callback=progress_callback,
        )
        if result is not None:
            return result

    return _fetch_sequential_messages(
        url=url,
        chat_config=chat_config,
        progress_callback=progress_callback,
        chunk_size=chunk_size,
    )


def _fetch_sequential_messages(
    url: str,
    chat_config: Dict,
    progress_callback: Optional[ProgressCallback],
    chunk_size: int,
) -> List[ChatMessage]:
    loader = ChatLoader(request_timeout=chat_config["request_timeout"])
    messages: List[ChatMessage] = []
    processed = 0
    last_timestamp: Optional[float] = None
    chunk: List[ChatMessage] = []

    message_iter = loader.fetch_messages(
        url=url,
        message_limit=chat_config.get("message_limit"),
    )

    for msg in message_iter:
        chunk.append(msg)
        last_timestamp = msg.timestamp_seconds
        if len(chunk) >= chunk_size:
            messages.extend(chunk)
            processed += len(chunk)
            chunk.clear()
            if progress_callback:
                progress_callback(processed, last_timestamp)

    if chunk:
        messages.extend(chunk)
        processed += len(chunk)
        if progress_callback:
            progress_callback(processed, last_timestamp)

    return messages


def _fetch_parallel_messages(
    url: str,
    chat_config: Dict,
    youtube_config: Dict,
    progress_callback: Optional[ProgressCallback],
) -> Optional[List[ChatMessage]]:
    api_key = youtube_config.get("api_key")
    segment_seconds = int(youtube_config.get("segment_duration_seconds", 0))
    max_workers = int(youtube_config.get("parallel_segments", 1))
    if not api_key or segment_seconds <= 0 or max_workers <= 1:
        return None

    video_id = extract_video_id(url)
    if not video_id:
        return None

    try:
        duration = fetch_video_duration_seconds(video_id, api_key)
    except Exception:  # requests error or parsing error
        return None

    if not duration or duration <= segment_seconds:
        return None

    segments = _build_segments(duration, segment_seconds)
    if not segments:
        return None

    messages: List[ChatMessage] = []
    processed = 0

    def fetch_segment(segment: Tuple[int, Optional[int]]) -> List[ChatMessage]:
        start_sec, end_sec = segment
        loader = ChatLoader(request_timeout=chat_config["request_timeout"])
        start_label = _format_seconds(start_sec)
        end_label = _format_seconds(end_sec) if end_sec is not None else None
        iterator = loader.fetch_messages(
            url=url,
            start_time=start_label,
            end_time=end_label,
            message_limit=None,
        )
        return list(iterator)

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(fetch_segment, segment): segment for segment in segments}
            for future in as_completed(future_map):
                segment_messages = future.result()
                messages.extend(segment_messages)
                processed += len(segment_messages)
                if progress_callback:
                    last_ts = (
                        segment_messages[-1].timestamp_seconds if segment_messages else None
                    )
                    progress_callback(processed, last_ts)
    except Exception:
        return None

    messages.sort(key=lambda msg: msg.timestamp_seconds)
    limit = chat_config.get("message_limit")
    if limit:
        return messages[: int(limit)]
    return messages


def _build_segments(duration_seconds: int, segment_seconds: int) -> Sequence[Tuple[int, Optional[int]]]:
    segments: List[Tuple[int, Optional[int]]] = []
    start = 0
    while start < duration_seconds:
        end = min(duration_seconds, start + segment_seconds)
        segments.append((start, end))
        start = end
    return segments


def _format_seconds(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    total = max(0, int(value))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def _can_parallel_fetch(youtube_config: Dict) -> bool:
    return (
        bool(youtube_config.get("api_key"))
        and int(youtube_config.get("parallel_segments", 1)) > 1
        and int(youtube_config.get("segment_duration_seconds", 0)) > 0
    )


def analyze_messages(
    messages: List[ChatMessage],
    keyword: Optional[str],
    cps_config: Dict,
    spike_config: Dict,
) -> Dict:
    analyzer = CPSAnalyzer(
        bucket_size_seconds=cps_config["bucket_size_seconds"],
        smoothing_window_seconds=cps_config["smoothing_window_seconds"],
        smoothing_average_window=cps_config.get("smoothing_average_window", 6),
    )
    detector = SpikeDetector(
        min_prominence=spike_config["min_prominence"],
        min_gap_seconds=spike_config["min_gap_seconds"],
        pre_start_buffer_seconds=spike_config.get("pre_start_buffer_seconds", 0.0),
    )

    result = analyzer.analyze(messages, keyword=keyword)
    target_series = result.smoothed_keyword if keyword else result.smoothed_total
    spikes = detector.detect(result.time_axis, target_series)

    return {
        "series": {
            "time_axis": result.time_axis.tolist(),
            "total": result.total_cps.tolist(),
            "member": result.member_cps.tolist(),
            "keyword": result.keyword_cps.tolist(),
            "smoothed_total": result.smoothed_total.tolist(),
            "smoothed_keyword": result.smoothed_keyword.tolist(),
        },
        "spikes": [
            {
                "start_time": spike.start_time,
                "peak_time": spike.peak_time,
                "peak_value": spike.peak_value,
            }
            for spike in spikes
        ],
    }
