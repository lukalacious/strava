"""Threshold auto-detection. FTP and threshold pace are time series, not constants.

Estimates are derived from the rolling mean-maximal curve and stored as a dated
history (see store layer). Manual overrides are first-class.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from .power import estimate_cp_wprime_from_streams, mean_maximal_power
from .running import grade_adjusted_speed, normalized_power


def estimate_ftp_from_power(
    power_w: Sequence[float], sample_rate_hz: float = 1.0
) -> Optional[float]:
    """Estimate FTP as 0.95 × best 20-minute power (classic field-test proxy)."""
    mmp20 = mean_maximal_power(power_w, 1200, sample_rate_hz)
    if np.isnan(mmp20):
        return None
    return float(0.95 * mmp20)


def estimate_ftp_from_cp(
    power_w: Sequence[float], sample_rate_hz: float = 1.0
) -> Optional[float]:
    """Estimate FTP from Critical Power (CP ≈ FTP for ~40–60 min efforts)."""
    cp, _ = estimate_cp_wprime_from_streams(power_w, sample_rate_hz=sample_rate_hz)
    return None if np.isnan(cp) else float(cp)


def estimate_threshold_pace(
    speed_ms: Sequence[float],
    grade: Sequence[float],
    sample_rate_hz: float = 1.0,
) -> Optional[float]:
    """Estimate threshold pace (as speed, m/s) ≈ best grade-adjusted 30 min effort.

    Uses the normalized graded speed over the best continuous 30-minute window.
    """
    gas = grade_adjusted_speed(speed_ms, grade)
    best = mean_maximal_power(gas, 1800, sample_rate_hz)  # MMP algo == best avg
    if np.isnan(best):
        # Fall back to a shorter window for shorter runs.
        best = mean_maximal_power(gas, 600, sample_rate_hz)
    return None if np.isnan(best) else float(best)
