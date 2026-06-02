"""Parse Strava bulk-export `.fit` files into canonical Streams + summary."""
from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import numpy as np

from ..models import ActivitySummary, Streams
from .streams import canonicalize

_SEMICIRCLE = 180.0 / 2**31  # FIT lat/long unit -> degrees

# FIT 'record' field -> canonical channel name (first present wins).
_FIELD_MAP = {
    "power_w": ("power",),
    "hr_bpm": ("heart_rate",),
    "speed_ms": ("enhanced_speed", "speed"),
    "altitude_m": ("enhanced_altitude", "altitude"),
    "distance_m": ("distance",),
    "cadence_rpm": ("cadence",),
    "temperature_c": ("temperature",),
}

_SPORT_MAP = {"cycling": "Ride", "running": "Run", "run": "Run", "ride": "Ride"}


def _open(path: Path):
    raw = path.read_bytes()
    if path.suffix == ".gz" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    from fitparse import FitFile

    return FitFile(raw)


def parse_fit(path: str | Path, activity_id: str | None = None) -> Tuple[ActivitySummary, Streams]:
    """Return (summary, canonical 1 Hz streams) for a `.fit`/`.fit.gz` file."""
    path = Path(path)
    activity_id = activity_id or path.stem.replace(".fit", "")
    fit = _open(path)

    times: list[float] = []
    cols: dict[str, list[float]] = {k: [] for k in _FIELD_MAP}
    lat: list[float] = []
    lng: list[float] = []
    have_latlng = False
    t0 = None

    for rec in fit.get_messages("record"):
        values = {d.name: d.value for d in rec}
        ts = values.get("timestamp")
        if ts is None:
            continue
        if t0 is None:
            t0 = ts
        times.append((ts - t0).total_seconds())
        for canon, candidates in _FIELD_MAP.items():
            val = next((values[c] for c in candidates if values.get(c) is not None), np.nan)
            cols[canon].append(float(val) if val is not None else np.nan)
        plat, plng = values.get("position_lat"), values.get("position_long")
        if plat is not None and plng is not None:
            lat.append(plat * _SEMICIRCLE); lng.append(plng * _SEMICIRCLE); have_latlng = True
        else:
            lat.append(np.nan); lng.append(np.nan)

    if not times:
        raise ValueError(f"No record messages in {path}")

    # Drop all-NaN channels so canonicalize doesn't carry dead columns.
    channels = {k: v for k, v in cols.items() if np.any(~np.isnan(v))}
    latlng = np.column_stack([lat, lng]) if have_latlng else None
    streams = canonicalize(times, channels, latlng=latlng)

    summary = _summary_from_fit(fit, activity_id, t0, streams)
    return summary, streams


def _summary_from_fit(fit, activity_id, t0, streams: Streams) -> ActivitySummary:
    sport = "Ride"
    distance = elapsed = moving = ascent = float("nan")
    start_time = (t0 or datetime.now(timezone.utc))
    for ses in fit.get_messages("session"):
        v = {d.name: d.value for d in ses}
        sport = _SPORT_MAP.get(str(v.get("sport", "")).lower(), sport)
        distance = float(v.get("total_distance") or distance)
        elapsed = float(v.get("total_elapsed_time") or elapsed)
        moving = float(v.get("total_timer_time") or moving)
        ascent = float(v.get("total_ascent") or ascent)
        if v.get("start_time"):
            start_time = v["start_time"]
        break
    if isinstance(start_time, datetime) and start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    # Fall back to stream-derived values where the session was silent.
    if np.isnan(distance) and streams.distance_m is not None:
        distance = float(np.nanmax(streams.distance_m))
    if np.isnan(elapsed):
        elapsed = float(len(streams))
    return ActivitySummary(
        activity_id=activity_id, sport=sport, start_time=start_time,
        distance_m=distance, elapsed_time_s=elapsed, moving_time_s=moving,
        total_ascent_m=ascent, source="export",
    )
