"""Performance Management Chart: unified cross-sport CTL / ATL / TSB.

Bike TSS and run rTSS sum into a single daily load (run load is multiplied by a
single tunable ``rtss_scale`` so cross-sport load can be recalibrated against
perceived effort). One CTL/ATL/TSB series, not three.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd

CTL_DAYS = 42
ATL_DAYS = 7


def daily_load(
    bike_tss_by_date: Mapping[str, float],
    run_rtss_by_date: Mapping[str, float],
    rtss_scale: float = 1.0,
) -> "pd.Series":
    """Unified daily training load = ΣTSS + rtss_scale·ΣrTSS, on a gap-free date index."""
    dates = set(bike_tss_by_date) | set(run_rtss_by_date)
    if not dates:
        return pd.Series(dtype="float64")
    idx = pd.to_datetime(sorted(dates))
    full = pd.date_range(idx.min(), idx.max(), freq="D")
    bike = pd.Series({pd.Timestamp(k): v for k, v in bike_tss_by_date.items()}).reindex(full, fill_value=0.0)
    run = pd.Series({pd.Timestamp(k): v for k, v in run_rtss_by_date.items()}).reindex(full, fill_value=0.0)
    return (bike + rtss_scale * run).astype("float64")


def _ewma(load: "pd.Series", time_constant_days: int) -> "pd.Series":
    """Impulse-response EWMA: x_t = x_{t-1} + (load_t - x_{t-1})·(1 - e^(-1/tc))."""
    alpha = 1.0 - math.exp(-1.0 / time_constant_days)
    out = np.zeros(len(load), dtype="float64")
    prev = 0.0
    vals = load.to_numpy()
    for i, v in enumerate(vals):
        prev = prev + (v - prev) * alpha
        out[i] = prev
    return pd.Series(out, index=load.index)


@dataclass
class PMC:
    load: "pd.Series"
    ctl: "pd.Series"      # fitness
    atl: "pd.Series"      # fatigue
    tsb: "pd.Series"      # form (yesterday's CTL - ATL)
    ramp_7d: "pd.Series"  # ΔCTL over trailing 7 days


def performance_management_chart(load: "pd.Series") -> PMC:
    """Compute CTL/ATL/TSB/ramp from a gap-free daily load series."""
    ctl = _ewma(load, CTL_DAYS)
    atl = _ewma(load, ATL_DAYS)
    # TSB (form) is yesterday's fitness minus yesterday's fatigue.
    tsb = (ctl.shift(1) - atl.shift(1)).fillna(0.0)
    ramp = ctl - ctl.shift(7)
    return PMC(load=load, ctl=ctl, atl=atl, tsb=tsb, ramp_7d=ramp)


def form_band(tsb: float) -> Tuple[str, str]:
    """Map a TSB value to a (band, one-line verdict)."""
    if np.isnan(tsb):
        return "unknown", "Not enough data to assess form."
    if tsb > 15:
        return "fresh", "Well rested — peaked, but fitness may be slipping if held too long."
    if tsb > 5:
        return "fresh", "Rested and race-ready."
    if tsb >= -10:
        return "neutral", "Balanced — productive training zone."
    if tsb >= -30:
        return "fatigued", "Carrying fatigue — normal in a build block; watch recovery."
    return "very fatigued", "Deep fatigue — back off to avoid non-functional overreaching."


def ramp_flag(ramp_7d: float, threshold: float = 6.0) -> bool:
    """True if 7-day CTL ramp exceeds the overload/injury-guard threshold."""
    return bool(np.isfinite(ramp_7d) and ramp_7d > threshold)


def current_status(pmc: PMC, ramp_threshold: float = 6.0) -> Dict[str, object]:
    """Latest-day snapshot: CTL/ATL/TSB, form band+verdict, ramp flag."""
    if len(pmc.ctl) == 0:
        return {}
    tsb_now = float(pmc.tsb.iloc[-1])
    band, verdict = form_band(tsb_now)
    ramp_now = float(pmc.ramp_7d.iloc[-1]) if len(pmc.ramp_7d) else float("nan")
    return {
        "date": str(pmc.ctl.index[-1].date()),
        "ctl": round(float(pmc.ctl.iloc[-1]), 1),
        "atl": round(float(pmc.atl.iloc[-1]), 1),
        "tsb": round(tsb_now, 1),
        "form_band": band,
        "verdict": verdict,
        "ramp_7d": round(ramp_now, 1),
        "ramp_warning": ramp_flag(ramp_now, ramp_threshold),
    }
