"""Normalise heterogeneous raw records into canonical 1 Hz :class:`Streams`.

Both `.fit` files and Strava MCP stream payloads land here. Everything is
resampled onto a uniform integer-second grid so the compute layer can assume
1 Hz sampling and a constant dt.
"""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
import pandas as pd

from ..models import Streams

# Channels interpolated continuously vs. forward-filled / zero-filled.
_CONTINUOUS = ("hr_bpm", "speed_ms", "altitude_m", "distance_m", "cadence_rpm", "temperature_c")


def canonicalize(
    time_s: Sequence[float],
    channels: Dict[str, Sequence[float]],
    latlng: Sequence[Sequence[float]] | None = None,
) -> Streams:
    """Resample raw samples onto a gap-free 1 Hz grid.

    Args:
        time_s: sample timestamps in seconds (need not start at 0 or be uniform).
        channels: mapping of canonical channel name -> raw values.
        latlng: optional (N,2) lat/lng.

    Power gaps become 0 W (coasting); other channels are time-interpolated.
    """
    t = np.asarray(time_s, dtype="float64")
    t = t - t[0]                                  # zero-base
    n = int(np.floor(t[-1])) + 1
    grid = np.arange(n, dtype="float64")

    df = pd.DataFrame({"t": t})
    for name, values in channels.items():
        df[name] = np.asarray(values, dtype="float64")
    df = df.drop_duplicates(subset="t").set_index("t")

    out: Dict[str, np.ndarray] = {"time_s": grid}
    for name in df.columns:
        series = df[name].reindex(df.index.union(grid)).interpolate(method="index")
        series = series.reindex(grid)
        if name == "power_w":
            series = series.fillna(0.0)           # coasting, not missing fitness
        out[name] = series.to_numpy()

    if latlng is not None:
        ll = np.asarray(latlng, dtype="float64")
        lat = pd.Series(ll[:, 0], index=df.index[: len(ll)]).reindex(grid, method="nearest")
        lng = pd.Series(ll[:, 1], index=df.index[: len(ll)]).reindex(grid, method="nearest")
        out["latlng"] = np.column_stack([lat.to_numpy(), lng.to_numpy()])

    return Streams(**out)
