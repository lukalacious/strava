"""Aerobic decoupling (Pw:Hr for cycling, Pa:Hr for running).

Decoupling measures how much the output-to-HR efficiency ratio fades from the
first half of an effort to the second. >5% indicates aerobic decoupling
(fatigue / insufficient aerobic base for the effort).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np


def decoupling_pct(
    output: Sequence[float],
    hr_bpm: Sequence[float],
    mask: Optional[Sequence[bool]] = None,
    min_output: float = 0.0,
) -> float:
    """Percentage drift in (output / HR) from first to second half.

    Args:
        output: power (W) for cycling, or speed (m/s) for running.
        hr_bpm: heart-rate stream.
        mask: optional boolean mask of samples to include (e.g. moving).
        min_output: ignore samples with output at/below this (e.g. 50 W coasting).

    Returns:
        Positive % = efficiency dropped in the second half (decoupled).
        ``(ratio_first - ratio_second) / ratio_second · 100`` (TrainingPeaks
        convention: drift relative to the second half).
    """
    out = np.asarray(output, dtype="float64")
    hr = np.asarray(hr_bpm, dtype="float64")
    n = min(out.size, hr.size)
    out, hr = out[:n], hr[:n]

    valid = np.isfinite(out) & np.isfinite(hr) & (hr > 0) & (out > min_output)
    if mask is not None:
        valid &= np.asarray(mask, dtype=bool)[:n]
    if valid.sum() < 4:
        return float("nan")

    idx = np.where(valid)[0]
    half = idx.size // 2
    first, second = idx[:half], idx[half:]
    if first.size == 0 or second.size == 0:
        return float("nan")

    ratio_first = np.mean(out[first]) / np.mean(hr[first])
    ratio_second = np.mean(out[second]) / np.mean(hr[second])
    if ratio_second == 0:
        return float("nan")
    return float((ratio_first - ratio_second) / ratio_second * 100.0)
