"""Canonical data model for the training dashboard.

Everything downstream operates on :class:`Streams` — per-second, metric-unit
arrays. Raw `.fit`/MCP data is normalised into this shape exactly once by the
ingest layer; the compute layer never touches raw files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class Streams:
    """Per-second activity streams, resampled to a uniform 1 Hz grid.

    All present arrays share the same length. Missing channels are ``None``.
    Units are strictly metric: power W, speed m/s, altitude/distance m,
    HR bpm, cadence rpm, temperature degC.
    """

    time_s: np.ndarray                      # seconds from start, 0..N-1
    power_w: Optional[np.ndarray] = None
    hr_bpm: Optional[np.ndarray] = None
    speed_ms: Optional[np.ndarray] = None
    altitude_m: Optional[np.ndarray] = None
    distance_m: Optional[np.ndarray] = None
    cadence_rpm: Optional[np.ndarray] = None
    temperature_c: Optional[np.ndarray] = None
    latlng: Optional[np.ndarray] = None     # shape (N, 2)

    def __len__(self) -> int:
        return int(self.time_s.shape[0])

    @property
    def sample_rate_hz(self) -> float:
        if len(self) < 2:
            return 1.0
        dt = float(np.median(np.diff(self.time_s)))
        return 1.0 / dt if dt > 0 else 1.0

    def has(self, channel: str) -> bool:
        arr = getattr(self, channel, None)
        return arr is not None and np.any(~np.isnan(np.asarray(arr, dtype="float64")))

    def moving_mask(self, speed_threshold_ms: float = 0.5) -> np.ndarray:
        """Boolean mask of moving samples (speed above a small threshold)."""
        if self.speed_ms is None:
            return np.ones(len(self), dtype=bool)
        sp = np.asarray(self.speed_ms, dtype="float64")
        return np.nan_to_num(sp, nan=0.0) > speed_threshold_ms

    def grade(self, smooth_s: int = 20) -> np.ndarray:
        """Instantaneous gradient (rise/run, dimensionless) from altitude+distance.

        Both are smoothed over ``smooth_s`` seconds before differencing to avoid
        GPS/barometric noise blowing up the gradient.
        """
        if self.altitude_m is None or self.distance_m is None:
            return np.zeros(len(self))
        import pandas as pd

        win = max(1, int(round(smooth_s * self.sample_rate_hz)))
        alt = pd.Series(self.altitude_m, dtype="float64").rolling(win, min_periods=1, center=True).mean().to_numpy()
        dist = pd.Series(self.distance_m, dtype="float64").rolling(win, min_periods=1, center=True).mean().to_numpy()
        d_alt = np.gradient(alt)
        d_dist = np.gradient(dist)
        with np.errstate(divide="ignore", invalid="ignore"):
            grade = np.where(d_dist > 0.1, d_alt / d_dist, 0.0)
        return np.clip(np.nan_to_num(grade), -0.45, 0.45)


@dataclass
class ActivitySummary:
    """Identity + summary fields for one activity (one row in the DB index)."""

    activity_id: str
    sport: str                              # "Ride" | "Run" | ...
    start_time: datetime
    name: str = ""
    distance_m: float = float("nan")
    elapsed_time_s: float = float("nan")
    moving_time_s: float = float("nan")
    total_ascent_m: float = float("nan")
    source: str = "export"                  # "export" | "mcp"


@dataclass
class DerivedMetrics:
    """Reduced, write-once metrics for one activity (cached by activity_id)."""

    activity_id: str
    sport: str
    date: str                               # ISO date (local), the PMC bucket
    duration_s: float
    # Cycling (power)
    np_w: float = float("nan")
    if_: float = float("nan")
    tss: float = float("nan")
    avg_power_w: float = float("nan")
    ef: float = float("nan")
    # Running (pace)
    ngp_ms: float = float("nan")
    rtss: float = float("nan")
    avg_speed_ms: float = float("nan")
    # Common
    avg_hr_bpm: float = float("nan")
    decoupling_pct: float = float("nan")
    # Threshold used at compute time (for full reproducibility)
    ftp_w_used: float = float("nan")
    threshold_pace_ms_used: float = float("nan")
    # JSON blobs (stored as TEXT): power-duration bests, zone time, EF/hour
    mmp_json: str = "{}"
    zone_time_json: str = "{}"
    ef_series_json: str = "[]"


@dataclass
class ThresholdPoint:
    """A dated threshold estimate (FTP or threshold pace). A time series."""

    date: str
    kind: str                               # "ftp_w" | "threshold_pace_ms"
    value: float
    method: str                             # "auto:0.95x20min" | "auto:cp" | "manual"
