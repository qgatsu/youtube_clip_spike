from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class Spike:
    start_time: float
    peak_time: float
    peak_value: float


class SpikeDetector:
    def __init__(
        self,
        min_prominence: float = 2.0,
        min_gap_seconds: float = 10.0,
        pre_start_buffer_seconds: float = 0.0,
    ):
        self.min_prominence = min_prominence
        self.min_gap_seconds = min_gap_seconds
        self.pre_start_buffer_seconds = max(pre_start_buffer_seconds, 0.0)

    def detect(self, time_axis: np.ndarray, smoothed_series: np.ndarray) -> List[Spike]:
        if smoothed_series.size == 0:
            return []

        bucket_interval = self._estimate_bucket_interval(time_axis)
        buffer_buckets = (
            int(
                max(
                    1,
                    round(
                        self.pre_start_buffer_seconds / max(bucket_interval, 1e-6)
                    ),
                )
            )
            if self.pre_start_buffer_seconds > 0
            else 0
        )

        baseline = np.mean(smoothed_series)
        std = np.std(smoothed_series)
        threshold = baseline + self.min_prominence * max(std, 1e-6)

        spikes: List[Spike] = []
        in_spike = False
        start_idx = 0
        last_peak_time = -np.inf

        for idx, value in enumerate(smoothed_series):
            if value >= threshold and not in_spike:
                in_spike = True
                start_idx = (
                    self._find_rising_start_idx(smoothed_series, idx, buffer_buckets)
                    if buffer_buckets
                    else idx
                )
            elif value < threshold and in_spike:
                peak_idx = int(np.argmax(smoothed_series[start_idx:idx]) + start_idx)
                peak_time = time_axis[peak_idx]
                if peak_time - last_peak_time >= self.min_gap_seconds:
                    spikes.append(
                        Spike(
                            start_time=time_axis[start_idx],
                            peak_time=peak_time,
                            peak_value=float(smoothed_series[peak_idx]),
                        )
                    )
                    last_peak_time = peak_time
                in_spike = False

        if in_spike:
            peak_idx = int(np.argmax(smoothed_series[start_idx:]) + start_idx)
            peak_time = time_axis[peak_idx]
            if peak_time - last_peak_time >= self.min_gap_seconds:
                spikes.append(
                    Spike(
                        start_time=time_axis[start_idx],
                        peak_time=peak_time,
                        peak_value=float(smoothed_series[peak_idx]),
                    )
                )

        return spikes

    @staticmethod
    def _estimate_bucket_interval(time_axis: np.ndarray) -> float:
        if time_axis.size < 2:
            return 1.0
        diffs = np.diff(time_axis)
        positive = diffs[diffs > 0]
        if positive.size == 0:
            return 1.0
        return float(np.median(positive))

    @staticmethod
    def _find_rising_start_idx(
        series: np.ndarray, idx: int, buffer_buckets: int
    ) -> int:
        lower_bound = max(0, idx - buffer_buckets)
        cursor = idx
        while cursor > lower_bound:
            prev_idx = cursor - 1
            if series[prev_idx] <= series[cursor]:
                cursor -= 1
            else:
                break
        return cursor
