"""Training-intensity distribution: power & HR zones, time-in-zone, polarization."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

# Coggan 7-zone power model as fractions of FTP (upper bounds; Z7 open-ended).
COGGAN_POWER_ZONES = [
    ("Z1 Active Recovery", 0.55),
    ("Z2 Endurance", 0.75),
    ("Z3 Tempo", 0.90),
    ("Z4 Threshold", 1.05),
    ("Z5 VO2max", 1.20),
    ("Z6 Anaerobic", 1.50),
    ("Z7 Neuromuscular", np.inf),
]


def time_in_power_zones(
    power_w: Sequence[float], ftp_w: float, sample_rate_hz: float = 1.0
) -> Dict[str, float]:
    """Seconds spent in each Coggan power zone."""
    p = np.nan_to_num(np.asarray(power_w, dtype="float64"), nan=0.0)
    dt = 1.0 / sample_rate_hz
    edges = [f * ftp_w for _, f in COGGAN_POWER_ZONES]
    out: Dict[str, float] = {}
    lower = 0.0
    for (name, _), upper in zip(COGGAN_POWER_ZONES, edges):
        out[name] = float(np.sum((p >= lower) & (p < upper)) * dt)
        lower = upper
    return out


def time_in_hr_zones(
    hr_bpm: Sequence[float], zone_edges_bpm: Sequence[float], labels: Optional[List[str]] = None,
    sample_rate_hz: float = 1.0,
) -> Dict[str, float]:
    """Seconds in each HR zone. ``zone_edges_bpm`` are upper bounds; last is open."""
    hr = np.asarray(hr_bpm, dtype="float64")
    valid = np.isfinite(hr) & (hr > 0)
    hr = hr[valid]
    dt = 1.0 / sample_rate_hz
    edges = list(zone_edges_bpm) + [np.inf]
    labels = labels or [f"Z{i+1}" for i in range(len(edges))]
    out: Dict[str, float] = {}
    lower = 0.0
    for label, upper in zip(labels, edges):
        out[label] = float(np.sum((hr >= lower) & (hr < upper)) * dt)
        lower = upper
    return out


def polarization(
    power_w: Sequence[float], ftp_w: float, sample_rate_hz: float = 1.0,
    vt1_frac: float = 0.75, vt2_frac: float = 1.0,
) -> dict:
    """3-zone polarization check against an ~80/20 target.

    Z1 = below VT1 (easy), Z2 = VT1..VT2 ("gray zone"), Z3 = above VT2 (hard).
    Returns percentages plus an 80/20 verdict and a gray-zone warning.
    """
    p = np.nan_to_num(np.asarray(power_w, dtype="float64"), nan=0.0)
    p = p[p > 0]
    if p.size == 0:
        return {"z1_pct": float("nan"), "z2_pct": float("nan"), "z3_pct": float("nan"),
                "verdict": "no data", "gray_zone_warning": False}
    lo, hi = vt1_frac * ftp_w, vt2_frac * ftp_w
    total = p.size
    z1 = np.sum(p < lo) / total * 100
    z2 = np.sum((p >= lo) & (p < hi)) / total * 100
    z3 = np.sum(p >= hi) / total * 100
    gray = z2 > 35.0
    if z1 >= 75 and z3 >= 10:
        verdict = "polarized (~80/20)"
    elif z2 > 35:
        verdict = "too much gray zone — threshold-heavy"
    else:
        verdict = "moderately polarized"
    return {"z1_pct": float(z1), "z2_pct": float(z2), "z3_pct": float(z3),
            "verdict": verdict, "gray_zone_warning": bool(gray)}
