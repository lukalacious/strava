"""Power-metric tests with analytically-derived expected values.

These validate the math without depending on any external 'truth' source: for
constant inputs the closed-form answers are exact.
"""
import numpy as np
import pytest

from trainingdash.compute import power as P


def test_np_of_constant_power_is_that_power():
    # 30-min ride at a flat 200 W → NP == 200.
    p = np.full(1800, 200.0)
    assert P.normalized_power(p) == pytest.approx(200.0, abs=1e-6)


def test_if_and_tss_one_hour_at_ftp_is_100():
    ftp = 250.0
    p = np.full(3600, ftp)
    np_w = P.normalized_power(p)
    assert P.intensity_factor(np_w, ftp) == pytest.approx(1.0, abs=1e-6)
    # TSS for exactly one hour at FTP is 100 by definition.
    assert P.tss(3600, np_w, ftp) == pytest.approx(100.0, abs=1e-6)


def test_tss_scales_with_duration_and_intensity():
    ftp = 250.0
    # Half an hour at FTP → 50 TSS.
    assert P.tss(1800, ftp, ftp) == pytest.approx(50.0, abs=1e-6)
    # One hour at 0.8·FTP → IF 0.8 → 64 TSS (100·0.8²).
    assert P.tss(3600, 0.8 * ftp, ftp) == pytest.approx(64.0, abs=1e-6)


def test_np_greater_than_average_for_variable_power():
    # Alternating hard/easy: NP must exceed the simple average.
    p = np.tile(np.concatenate([np.full(60, 300.0), np.full(60, 100.0)]), 30)
    assert P.normalized_power(p) > np.mean(p)


def test_mean_maximal_power_picks_the_best_window():
    # 100 W baseline with a 60 s, 400 W spike → MMP(60) == 400.
    p = np.full(1200, 100.0)
    p[600:660] = 400.0
    assert P.mean_maximal_power(p, 60) == pytest.approx(400.0, abs=1e-6)
    # A 120 s window straddling the spike averages down.
    assert P.mean_maximal_power(p, 120) < 400.0


def test_cp_wprime_linear_fit_recovers_parameters():
    # Construct points exactly on P = W'/t + CP with CP=250, W'=20000 J.
    cp_true, w_true = 250.0, 20000.0
    durations = [180, 300, 600, 720, 1200]
    powers = [w_true / t + cp_true for t in durations]
    cp, w = P.fit_cp_wprime(durations, powers)
    assert cp == pytest.approx(cp_true, rel=1e-6)
    assert w == pytest.approx(w_true, rel=1e-6)


def test_cp_requires_three_points():
    cp, w = P.fit_cp_wprime([300, 1200], [300, 260])
    assert np.isnan(cp) and np.isnan(w)


def test_efficiency_factor():
    assert P.efficiency_factor(190.0, 125.0) == pytest.approx(1.52, abs=1e-6)
    assert np.isnan(P.efficiency_factor(190.0, 0.0))


def test_ef_series_segments_hourly():
    # Two hours: HR rises in hour 2 at the same power → EF drops segment-to-segment.
    p = np.full(7200, 200.0)
    hr = np.concatenate([np.full(3600, 130.0), np.full(3600, 145.0)])
    series = P.ef_series(p, hr, segment_s=3600)
    assert len(series) == 2
    assert series[0]["ef"] > series[1]["ef"]
