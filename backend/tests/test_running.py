"""Running-metric tests: Minetti grade adjustment, NGP, rTSS."""
import numpy as np
import pytest

from trainingdash.compute import running as R


def test_minetti_flat_cost_is_baseline():
    assert R.minetti_cost(np.array([0.0]))[0] == pytest.approx(3.6, abs=1e-9)


def test_grade_adjustment_makes_uphill_equivalent_faster():
    # 3 m/s on a 10% climb maps to a faster equivalent flat speed.
    flat = R.grade_adjusted_speed([3.0], [0.0])[0]
    uphill = R.grade_adjusted_speed([3.0], [0.10])[0]
    assert flat == pytest.approx(3.0, abs=1e-9)
    assert uphill > 3.0


def test_grade_adjustment_matches_hand_calc():
    # GAP factor at 10% = C(0.10)/C(0).
    c = R.minetti_cost(np.array([0.10]))[0]
    expected = 3.0 * c / 3.6
    assert R.grade_adjusted_speed([3.0], [0.10])[0] == pytest.approx(expected, rel=1e-9)


def test_ngp_constant_flat_speed():
    speed = np.full(1800, 3.5)
    grade = np.zeros(1800)
    assert R.normalized_graded_speed(speed, grade) == pytest.approx(3.5, abs=1e-6)


def test_pace_conversion():
    # 1000 m at 3.333 m/s → 5:00/km.
    assert R.speed_to_pace_min_km(1000 / 300.0) == pytest.approx(5.0, abs=1e-6)


def test_rtss_one_hour_at_threshold_is_100():
    thr = 3.5  # m/s threshold pace
    speed = np.full(3600, thr)
    grade = np.zeros(3600)
    ngp = R.normalized_graded_speed(speed, grade)
    assert R.intensity_factor_run(ngp, thr) == pytest.approx(1.0, abs=1e-6)
    assert R.rtss(3600, ngp, thr) == pytest.approx(100.0, abs=1e-6)


def test_rtss_scales_with_intensity():
    thr = 3.5
    # One hour at 0.9·threshold speed → IF 0.9 → 81 rTSS.
    assert R.rtss(3600, 0.9 * thr, thr) == pytest.approx(81.0, abs=1e-6)
