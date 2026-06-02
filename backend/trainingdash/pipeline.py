"""Ingest → reduce → cache, plus the PMC build over cached metrics.

Idempotent: an activity already in the derived-metrics cache is skipped unless
``force=True``. Reductions and raw streams are write-once.
"""
from __future__ import annotations

import json
from typing import Optional

import numpy as np

from .compute import decoupling, power, running, thresholds, zones
from .compute import pmc as pmc_mod
from .models import ActivitySummary, DerivedMetrics, Streams, ThresholdPoint
from .store import Store


def _activity_date(summary: ActivitySummary) -> str:
    return summary.start_time.date().isoformat()


def _effective_or_seed_ftp(store: Store, summary: ActivitySummary, streams: Streams) -> float:
    """Return FTP effective on the activity date, seeding from this ride if none."""
    date = _activity_date(summary)
    ftp = store.effective_threshold("ftp_w", date)
    if ftp is not None:
        return ftp
    est = thresholds.estimate_ftp_from_power(streams.power_w, streams.sample_rate_hz) \
        if streams.has("power_w") else None
    if est:
        store.add_threshold(ThresholdPoint(date, "ftp_w", est, "auto:0.95x20min"))
        return est
    return float("nan")


def _effective_or_seed_pace(store: Store, summary: ActivitySummary, streams: Streams) -> float:
    date = _activity_date(summary)
    thr = store.effective_threshold("threshold_pace_ms", date)
    if thr is not None:
        return thr
    if streams.has("speed_ms"):
        est = thresholds.estimate_threshold_pace(streams.speed_ms, streams.grade(), streams.sample_rate_hz)
        if est:
            store.add_threshold(ThresholdPoint(date, "threshold_pace_ms", est, "auto:best30min_gap"))
            return est
    return float("nan")


def reduce_streams(
    summary: ActivitySummary, streams: Streams, ftp_w: float, threshold_pace_ms: float,
    hr_zone_edges: Optional[list] = None,
) -> DerivedMetrics:
    """Compute all derived metrics for one activity from its streams + thresholds."""
    sr = streams.sample_rate_hz
    moving = streams.moving_mask()
    moving_s = float(moving.sum() / sr)
    m = DerivedMetrics(
        activity_id=summary.activity_id, sport=summary.sport,
        date=_activity_date(summary), duration_s=moving_s,
        ftp_w_used=ftp_w, threshold_pace_ms_used=threshold_pace_ms,
    )

    if streams.has("hr_bpm"):
        hr = np.asarray(streams.hr_bpm, dtype="float64")
        valid = np.isfinite(hr) & (hr > 0) & moving
        if valid.any():
            m.avg_hr_bpm = float(np.mean(hr[valid]))

    if summary.sport == "Ride" and streams.has("power_w"):
        p = streams.power_w
        m.np_w = power.normalized_power(p, sr)
        m.if_ = power.intensity_factor(m.np_w, ftp_w)
        m.tss = power.tss(moving_s, m.np_w, ftp_w)
        m.avg_power_w = float(np.mean(np.nan_to_num(np.asarray(p, dtype="float64"))[moving]))
        m.ef = power.efficiency_factor(m.np_w, m.avg_hr_bpm)
        m.decoupling_pct = decoupling.decoupling_pct(p, streams.hr_bpm, mask=moving, min_output=50) \
            if streams.has("hr_bpm") else float("nan")
        m.mmp_json = json.dumps(power.power_duration_curve(p, sample_rate_hz=sr))
        m.zone_time_json = json.dumps(zones.time_in_power_zones(p, ftp_w, sr)) if ftp_w and not np.isnan(ftp_w) else "{}"
        m.ef_series_json = json.dumps(power.ef_series(p, streams.hr_bpm, 3600, sr)) if streams.has("hr_bpm") else "[]"

    elif summary.sport == "Run" and streams.has("speed_ms"):
        sp, grade = streams.speed_ms, streams.grade()
        ngp = running.normalized_graded_speed(sp, grade, sr)
        m.ngp_ms = ngp
        m.rtss = running.rtss(moving_s, ngp, threshold_pace_ms)
        m.avg_speed_ms = float(np.mean(np.nan_to_num(np.asarray(sp, dtype="float64"))[moving]))
        m.decoupling_pct = decoupling.decoupling_pct(sp, streams.hr_bpm, mask=moving, min_output=0.5) \
            if streams.has("hr_bpm") else float("nan")
        if hr_zone_edges and streams.has("hr_bpm"):
            m.zone_time_json = json.dumps(zones.time_in_hr_zones(streams.hr_bpm, hr_zone_edges, sample_rate_hz=sr))
    return m


def process_activity(
    store: Store, summary: ActivitySummary, streams: Streams,
    force: bool = False, hr_zone_edges: Optional[list] = None,
) -> Optional[DerivedMetrics]:
    """Reduce + cache one activity. Skips if already processed (unless force)."""
    store.upsert_activity(summary)
    if store.is_processed(summary.activity_id) and not force:
        return None
    ftp = _effective_or_seed_ftp(store, summary, streams)
    pace = _effective_or_seed_pace(store, summary, streams)
    metrics = reduce_streams(summary, streams, ftp, pace, hr_zone_edges)
    store.upsert_derived(metrics)
    if not store.has_streams(summary.activity_id):
        store.save_streams(summary.activity_id, streams)   # write-once for drill-down
    return metrics


def build_pmc(store: Store, rtss_scale: float = 1.0) -> pmc_mod.PMC:
    """Assemble the unified PMC from all cached derived metrics."""
    rows = store.all_derived()
    bike: dict[str, float] = {}
    run: dict[str, float] = {}
    for r in rows:
        if r["sport"] == "Ride" and r["tss"] is not None and np.isfinite(r["tss"]):
            bike[r["date"]] = bike.get(r["date"], 0.0) + float(r["tss"])
        elif r["sport"] == "Run" and r["rtss"] is not None and np.isfinite(r["rtss"]):
            run[r["date"]] = run.get(r["date"], 0.0) + float(r["rtss"])
    load = pmc_mod.daily_load(bike, run, rtss_scale=rtss_scale)
    return pmc_mod.performance_management_chart(load)
