"""PMC tests: EWMA recurrence, unified load, ramp, form bands."""
import math

import numpy as np
import pandas as pd
import pytest

from trainingdash.compute import pmc as M


def test_daily_load_unifies_sports_and_fills_gaps():
    bike = {"2026-01-01": 100.0, "2026-01-03": 50.0}
    run = {"2026-01-02": 40.0}
    load = M.daily_load(bike, run, rtss_scale=1.0)
    # Gap-free Jan 1–3.
    assert list(load.index.date.astype(str)) == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert load.iloc[0] == 100.0
    assert load.iloc[1] == 40.0   # run day
    assert load.iloc[2] == 50.0


def test_rtss_scale_applies_to_runs_only():
    bike = {"2026-01-01": 100.0}
    run = {"2026-01-01": 50.0}
    load = M.daily_load(bike, run, rtss_scale=0.5)
    assert load.iloc[0] == 100.0 + 0.5 * 50.0


def test_ewma_converges_to_constant_load():
    # Constant daily load for a long time → CTL and ATL both approach it.
    load = pd.Series(100.0, index=pd.date_range("2025-01-01", periods=400, freq="D"))
    pmc = M.performance_management_chart(load)
    assert pmc.ctl.iloc[-1] == pytest.approx(100.0, abs=0.5)
    assert pmc.atl.iloc[-1] == pytest.approx(100.0, abs=0.01)
    # Form ≈ 0 when fully adapted.
    assert pmc.tsb.iloc[-1] == pytest.approx(0.0, abs=0.6)


def test_ewma_matches_manual_recurrence():
    load = pd.Series([100.0, 0.0, 0.0], index=pd.date_range("2026-01-01", periods=3))
    pmc = M.performance_management_chart(load)
    alpha = 1 - math.exp(-1 / M.ATL_DAYS)
    # ATL day 0: 0 + (100-0)·alpha
    a0 = 100.0 * alpha
    a1 = a0 + (0 - a0) * alpha
    assert pmc.atl.iloc[0] == pytest.approx(a0, abs=1e-9)
    assert pmc.atl.iloc[1] == pytest.approx(a1, abs=1e-9)


def test_tsb_is_yesterdays_ctl_minus_atl():
    load = pd.Series([100.0, 100.0, 100.0], index=pd.date_range("2026-01-01", periods=3))
    pmc = M.performance_management_chart(load)
    # Day 2 TSB == day 1 CTL - day 1 ATL.
    assert pmc.tsb.iloc[2] == pytest.approx(pmc.ctl.iloc[1] - pmc.atl.iloc[1], abs=1e-9)


def test_ramp_rate_over_7_days():
    load = pd.Series(80.0, index=pd.date_range("2025-06-01", periods=60, freq="D"))
    pmc = M.performance_management_chart(load)
    assert pmc.ramp_7d.iloc[-1] == pytest.approx(
        pmc.ctl.iloc[-1] - pmc.ctl.iloc[-8], abs=1e-9
    )


def test_form_bands_and_flag():
    assert M.form_band(10)[0] == "fresh"
    assert M.form_band(0)[0] == "neutral"
    assert M.form_band(-20)[0] == "fatigued"
    assert M.form_band(-40)[0] == "very fatigued"
    assert M.ramp_flag(8.0) is True
    assert M.ramp_flag(3.0) is False
