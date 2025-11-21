from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np

from .chat_loader import ChatMessage


@dataclass(frozen=True)
class CPSResult:
    time_axis: np.ndarray
    total_cps: np.ndarray
    member_cps: np.ndarray
    keyword_cps: np.ndarray
    smoothed_total: np.ndarray
    smoothed_keyword: np.ndarray


class CPSAnalyzer:
    def __init__(
        self,
        bucket_size_seconds: float = 1.0,
        smoothing_window_seconds: float = 5.0,
        smoothing_average_window: int = 6,
    ) -> None:
        self.bucket_size = bucket_size_seconds
        self.smoothing_window = max(1, int(smoothing_window_seconds / bucket_size_seconds))
        self.smoothing_average_window = max(1, smoothing_average_window)

    def analyze(self, messages: Iterable[ChatMessage], keyword: str | None = None) -> CPSResult:
        series = list(messages)
        if not series:
            empty = np.array([])
            return CPSResult(empty, empty, empty, empty, empty, empty)

        buckets = self._accumulate_counts(series, keyword=keyword)
        time_axis, total, member, keyword_counts = self._build_arrays(buckets)
        smoothed_total = self._smooth_series(total)
        smoothed_keyword = self._smooth_series(keyword_counts)
        return CPSResult(time_axis, total, member, keyword_counts, smoothed_total, smoothed_keyword)

    def _accumulate_counts(
        self, messages: Iterable[ChatMessage], keyword: str | None
    ) -> Dict[int, Dict[str, int]]:
        normalized_keyword = keyword.lower() if keyword else None
        buckets: Dict[int, Dict[str, int]] = {}
        for msg in messages:
            bucket_idx = int(msg.timestamp_seconds // self.bucket_size)
            bucket = buckets.setdefault(bucket_idx, {"total": 0, "member": 0, "keyword": 0})
            bucket["total"] += 1
            if msg.is_member:
                bucket["member"] += 1
            if normalized_keyword:
                text = msg.message.lower() if isinstance(msg.message, str) else ""
                if normalized_keyword in text:
                    bucket["keyword"] += 1
        return buckets

    def _build_arrays(
        self, buckets: Dict[int, Dict[str, int]]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        bucket_indices = sorted(buckets.keys())
        time_axis = np.array(bucket_indices, dtype=float) * self.bucket_size
        total = np.array([buckets[idx]["total"] for idx in bucket_indices], dtype=float)
        member = np.array([buckets[idx]["member"] for idx in bucket_indices], dtype=float)
        keyword = np.array([buckets[idx]["keyword"] for idx in bucket_indices], dtype=float)
        return time_axis, total, member, keyword

    def _smooth_series(self, series: np.ndarray) -> np.ndarray:
        if series.size == 0:
            return series
        window = np.ones(self.smoothing_window, dtype=float) / self.smoothing_window
        summed = np.convolve(series, window, mode="same")
        avg_window = np.ones(self.smoothing_average_window) / self.smoothing_average_window
        return np.convolve(summed, avg_window, mode="same")
