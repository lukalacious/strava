"""Running metrics — grade-adjusted pace (GAP/NGP) and rTSS.

Grade adjustment uses Minetti's energy-cost-of-running model, so uphill effort
is expressed as equivalent flat pace. Flat pace lies on climbs; GAP does not.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from .power import normalized_power  # NGP reuses the NP algorithm on speed

# Minetti et al. (2002), energy cost of running C(i) [J/kg/m], i = gradient.
_MINETTI = (155.4, -30.4, -43.3, 46.3, 19.5, 3.6)  # coeffs for i^5..i^0
_C0 = 3.6  # cost on the flat


def minetti_cost(grade: np.ndarray) -> np.ndarray:
    """Energy cost of running C(i) in J/kg/m for gradient array ``grade``."""
    i = np.clip(np.asarray(grade, dtype="float64"), -0.45, 0.45)
    a, b, c, d, e, f = _MINETTI
    return a * i**5 + b * i**4 + c * i**3 + d * i**2 + e * i + f


def grade_adjusted_speed(speed_ms: Sequence[float], grade: Sequence[float]) -> np.ndarray:
    """Convert actual speed to equivalent flat (grade-adjusted) speed.

    Uphill running costs more energy per metre, so a slow uphill pace maps to a
    faster equivalent flat pace: GAP_speed = speed · C(i)/C(0).
    """
    sp = np.nan_to_num(np.asarray(speed_ms, dtype="float64"), nan=0.0)
    ratio = minetti_cost(np.asarray(grade, dtype="float64")) / _C0
    return sp * ratio


def normalized_graded_speed(
    speed_ms: Sequence[float],
    grade: Sequence[float],
    sample_rate_hz: float = 1.0,
) -> float:
    """NGP as a speed (m/s): NP algorithm applied to grade-adjusted speed."""
    gas = grade_adjusted_speed(speed_ms, grade)
    return normalized_power(gas, sample_rate_hz)   # identical 30 s/^4 math


def speed_to_pace_min_km(speed_ms: float) -> float:
    """Convert m/s to running pace in minutes per kilometre."""
    if not speed_ms or np.isnan(speed_ms) or speed_ms <= 0:
        return float("nan")
    return (1000.0 / speed_ms) / 60.0


def intensity_factor_run(ngp_ms: float, threshold_pace_ms: float) -> float:
    """IF_run = NGP / threshold pace (both as speeds, m/s)."""
    if not threshold_pace_ms or np.isnan(threshold_pace_ms):
        return float("nan")
    return float(ngp_ms / threshold_pace_ms)


def rtss(duration_s: float, ngp_ms: float, threshold_pace_ms: float) -> float:
    """Running TSS = duration·NGP·IF_run / (threshold·3600) · 100.

    One hour exactly at threshold pace yields 100 by construction.
    """
    if not threshold_pace_ms or np.isnan(threshold_pace_ms) or np.isnan(ngp_ms):
        return float("nan")
    if_run = ngp_ms / threshold_pace_ms
    return float(duration_s * ngp_ms * if_run / (threshold_pace_ms * 3600.0) * 100.0)
