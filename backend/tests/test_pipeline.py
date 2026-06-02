"""End-to-end pipeline test on synthetic streams (no external files needed)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from trainingdash.ingest.streams import canonicalize
from trainingdash.models import ActivitySummary, Streams
from trainingdash.pipeline import build_pmc, process_activity
from trainingdash.store import Store


def _synthetic_ride(activity_id: str, date: str, watts: float = 200.0) -> tuple:
    n = 3600
    t = np.arange(n, dtype="float64")
    streams = Streams(
        time_s=t,
        power_w=np.full(n, watts),
        hr_bpm=np.full(n, 140.0),
        speed_ms=np.full(n, 8.0),
        altitude_m=np.linspace(100, 300, n),
        distance_m=np.cumsum(np.full(n, 8.0)),
    )
    summary = ActivitySummary(
        activity_id=activity_id, sport="Ride",
        start_time=datetime.fromisoformat(date).replace(tzinfo=timezone.utc),
        distance_m=float(streams.distance_m[-1]), elapsed_time_s=n, moving_time_s=n,
    )
    return summary, streams


def test_canonicalize_produces_1hz_grid():
    s = canonicalize([0, 2, 5], {"power_w": [100, 200, 300], "hr_bpm": [120, 130, 140]})
    assert s.sample_rate_hz == pytest.approx(1.0)
    assert len(s) == 6                       # seconds 0..5
    assert s.power_w[0] == pytest.approx(100.0)


def test_process_caches_and_is_idempotent(tmp_path):
    store = Store(tmp_path / "cache.sqlite")
    summary, streams = _synthetic_ride("a1", "2026-01-01T09:00:00")
    m = process_activity(store, summary, streams)
    assert m is not None
    assert store.is_processed("a1")
    # FTP auto-seeded (0.95 × 20-min MMP of 200 W == 190 W).
    assert store.effective_threshold("ftp_w", "2026-01-01") == pytest.approx(190.0, abs=1e-3)
    # Raw streams cached for drill-down.
    assert store.has_streams("a1")
    loaded = store.load_streams("a1")
    assert len(loaded) == len(streams)
    # Second call is a no-op (write-once).
    assert process_activity(store, summary, streams) is None
    store.close()


def test_derived_metrics_are_sane(tmp_path):
    store = Store(tmp_path / "cache.sqlite")
    summary, streams = _synthetic_ride("a1", "2026-01-01T09:00:00")
    m = process_activity(store, summary, streams)
    assert m.np_w == pytest.approx(200.0, abs=1e-3)     # constant power
    assert m.ef == pytest.approx(200.0 / 140.0, abs=1e-3)
    assert m.decoupling_pct == pytest.approx(0.0, abs=1e-6)
    store.close()


def test_build_pmc_over_multiple_days(tmp_path):
    store = Store(tmp_path / "cache.sqlite")
    for i in range(1, 15):
        summary, streams = _synthetic_ride(f"a{i}", f"2026-01-{i:02d}T09:00:00")
        process_activity(store, summary, streams)
    pmc = build_pmc(store, rtss_scale=1.0)
    assert len(pmc.ctl) == 14
    assert pmc.ctl.iloc[-1] > 0
    from trainingdash.compute.pmc import current_status
    status = current_status(pmc)
    assert status["form_band"] in {"fresh", "neutral", "fatigued", "very fatigued"}
    store.close()
