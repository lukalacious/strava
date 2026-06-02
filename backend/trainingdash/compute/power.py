"""Cycling power metrics — all per Coggan / Monod–Scherrer definitions.

Every function is pure: arrays in, numbers out. Nothing here reads files,
hits a network, or consults Strava's computed scores.
"""
from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

import numpy as np
import pandas as pd


def _clean(power_w: Sequence[float]) -> np.ndarray:
    """Coerce to float array, treating missing samples as 0 W (coasting)."""
    p = np.asarray(power_w, dtype="float64")
    return np.nan_to_num(p, nan=0.0)


def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    """Trailing rolling mean requiring a full window (leading values are NaN)."""
    return pd.Series(x, dtype="float64").rolling(window=window, min_periods=window).mean().to_numpy()


def normalized_power(power_w: Sequence[float], sample_rate_hz: float = 1.0) -> float:
    """Normalized Power (Coggan): 30 s rolling mean → ^4 → mean → ^(1/4)."""
    p = _clean(power_w)
    window = max(1, int(round(30 * sample_rate_hz)))
    if p.size < window:
        return float("nan")
    roll = rolling_mean(p, window)
    roll = roll[~np.isnan(roll)]
    if roll.size == 0:
        return float("nan")
    return float(np.mean(np.power(roll, 4)) ** 0.25)


def intensity_factor(np_w: float, ftp_w: float) -> float:
    """IF = NP / FTP."""
    if not ftp_w or np.isnan(ftp_w):
        return float("nan")
    return float(np_w / ftp_w)


def tss(duration_s: float, np_w: float, ftp_w: float) -> float:
    """Training Stress Score = duration·NP·IF / (FTP·3600) · 100.

    One hour exactly at FTP (NP == FTP) yields 100 by construction.
    """
    if not ftp_w or np.isnan(ftp_w) or np.isnan(np_w):
        return float("nan")
    if_ = np_w / ftp_w
    return float(duration_s * np_w * if_ / (ftp_w * 3600.0) * 100.0)


def mean_maximal_power(power_w: Sequence[float], duration_s: float, sample_rate_hz: float = 1.0) -> float:
    """Best average power sustained over any ``duration_s`` window (MMP)."""
    p = _clean(power_w)
    window = max(1, int(round(duration_s * sample_rate_hz)))
    if p.size < window:
        return float("nan")
    roll = rolling_mean(p, window)
    roll = roll[~np.isnan(roll)]
    if roll.size == 0:
        return float("nan")
    return float(np.max(roll))


def power_duration_curve(
    power_w: Sequence[float],
    durations_s: Iterable[float] = (5, 15, 30, 60, 180, 300, 480, 600, 720, 1200, 1800, 3600),
    sample_rate_hz: float = 1.0,
) -> Dict[int, float]:
    """Mean-maximal power at each duration. Keys are integer seconds."""
    out: Dict[int, float] = {}
    for d in durations_s:
        mmp = mean_maximal_power(power_w, d, sample_rate_hz)
        if not np.isnan(mmp):
            out[int(d)] = mmp
    return out


def fit_cp_wprime(
    durations_s: Sequence[float],
    powers_w: Sequence[float],
) -> Tuple[float, float]:
    """2-parameter Monod–Scherrer fit: P(t) = W'/t + CP.

    Linear in 1/t: regress P on (1/t); intercept = CP (W), slope = W' (J).
    Requires ≥3 points. Returns (CP_w, W_prime_j).
    """
    t = np.asarray(durations_s, dtype="float64")
    p = np.asarray(powers_w, dtype="float64")
    mask = (t > 0) & np.isfinite(p)
    t, p = t[mask], p[mask]
    if t.size < 3:
        return float("nan"), float("nan")
    x = 1.0 / t
    slope, intercept = np.polyfit(x, p, 1)   # P = slope·(1/t) + intercept
    return float(intercept), float(slope)    # CP, W'


def estimate_cp_wprime_from_streams(
    power_w: Sequence[float],
    durations_s: Sequence[float] = (180, 300, 600, 720, 1200),
    sample_rate_hz: float = 1.0,
) -> Tuple[float, float]:
    """CP/W' fit using mean-maximal power at multiple durations (3–20 min)."""
    pdc = {d: mean_maximal_power(power_w, d, sample_rate_hz) for d in durations_s}
    pdc = {d: v for d, v in pdc.items() if not np.isnan(v)}
    if len(pdc) < 3:
        return float("nan"), float("nan")
    return fit_cp_wprime(list(pdc.keys()), list(pdc.values()))


def efficiency_factor(np_w: float, avg_hr_bpm: float) -> float:
    """EF = NP / average HR. Higher = more aerobically efficient."""
    if not avg_hr_bpm or np.isnan(avg_hr_bpm) or avg_hr_bpm <= 0:
        return float("nan")
    return float(np_w / avg_hr_bpm)


def ef_series(
    power_w: Sequence[float],
    hr_bpm: Sequence[float],
    segment_s: float = 3600.0,
    sample_rate_hz: float = 1.0,
) -> list:
    """EF per time segment (default hourly), for within-activity EF drift.

    Returns a list of {"segment": i, "ef": value, "np_w": .., "avg_hr": ..}.
    """
    p = _clean(power_w)
    hr = np.asarray(hr_bpm, dtype="float64")
    n = p.size
    step = max(1, int(round(segment_s * sample_rate_hz)))
    out = []
    for i, start in enumerate(range(0, n, step)):
        seg_p = p[start:start + step]
        seg_hr = hr[start:start + step]
        valid = ~np.isnan(seg_hr) & (seg_hr > 0)
        if valid.sum() < step * 0.25:        # need a meaningful chunk
            continue
        seg_np = normalized_power(seg_p, sample_rate_hz)
        avg_hr = float(np.mean(seg_hr[valid]))
        out.append({"segment": i, "ef": efficiency_factor(seg_np, avg_hr),
                    "np_w": seg_np, "avg_hr": avg_hr})
    return out
