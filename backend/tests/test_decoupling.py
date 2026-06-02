"""Decoupling tests with hand-computed expected drift."""
import numpy as np
import pytest

from trainingdash.compute.decoupling import decoupling_pct


def test_no_decoupling_when_steady():
    power = np.full(3600, 200.0)
    hr = np.full(3600, 140.0)
    assert decoupling_pct(power, hr, min_output=50) == pytest.approx(0.0, abs=1e-6)


def test_positive_decoupling_when_hr_drifts_up():
    # Same power both halves; HR 140 → 150 in second half.
    # ratio_first = 200/140, ratio_second = 200/150.
    # decoupling = (rf - rs)/rs * 100 = (150/140 - 1)*100 = 7.142857%.
    power = np.full(3600, 200.0)
    hr = np.concatenate([np.full(1800, 140.0), np.full(1800, 150.0)])
    expected = (150 / 140 - 1) * 100
    assert decoupling_pct(power, hr, min_output=50) == pytest.approx(expected, abs=1e-6)


def test_negative_decoupling_when_hr_drops():
    power = np.full(3600, 200.0)
    hr = np.concatenate([np.full(1800, 150.0), np.full(1800, 140.0)])
    assert decoupling_pct(power, hr, min_output=50) < 0


def test_min_output_filters_coasting():
    # Second half is all coasting (0 W) → excluded, so first half only → 0%.
    power = np.concatenate([np.full(1800, 200.0), np.zeros(1800)])
    hr = np.concatenate([np.full(1800, 140.0), np.full(1800, 160.0)])
    assert decoupling_pct(power, hr, min_output=50) == pytest.approx(0.0, abs=1e-6)


def test_running_decoupling_uses_speed():
    speed = np.full(3600, 3.5)
    hr = np.concatenate([np.full(1800, 150.0), np.full(1800, 158.0)])
    expected = (158 / 150 - 1) * 100
    assert decoupling_pct(speed, hr, min_output=0.5) == pytest.approx(expected, abs=1e-6)
