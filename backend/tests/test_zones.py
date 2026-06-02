"""Zone distribution & polarization tests."""
import numpy as np
import pytest

from trainingdash.compute import zones as Z


def test_power_zone_time_sums_to_duration():
    p = np.concatenate([np.full(600, 100.0), np.full(600, 200.0), np.full(600, 320.0)])
    tiz = Z.time_in_power_zones(p, ftp_w=250.0)
    assert sum(tiz.values()) == pytest.approx(1800, abs=1e-6)
    # 100 W < 0.55·250=137.5 → Z1; 200 W in 0.75–0.90 band? 0.75·250=187.5, 0.90·250=225 → Z3 Tempo
    assert tiz["Z1 Active Recovery"] == pytest.approx(600, abs=1e-6)
    assert tiz["Z3 Tempo"] == pytest.approx(600, abs=1e-6)
    # 320 W > 1.20·250=300 and < 1.50·250=375 → Z6 Anaerobic
    assert tiz["Z6 Anaerobic"] == pytest.approx(600, abs=1e-6)


def test_hr_zone_time():
    hr = np.concatenate([np.full(300, 120.0), np.full(300, 150.0), np.full(300, 175.0)])
    tiz = Z.time_in_hr_zones(hr, [130, 160, 170], labels=["Z1", "Z2", "Z3", "Z4"])
    assert tiz["Z1"] == pytest.approx(300, abs=1e-6)   # 120 < 130
    assert tiz["Z2"] == pytest.approx(300, abs=1e-6)   # 150 in 130–160
    assert tiz["Z4"] == pytest.approx(300, abs=1e-6)   # 175 > 170


def test_polarization_detects_polarized():
    # 85% easy, 15% hard → polarized.
    p = np.concatenate([np.full(8500, 150.0), np.full(1500, 280.0)])  # ftp 250
    res = Z.polarization(p, ftp_w=250.0)
    assert res["z1_pct"] > 75 and res["z3_pct"] >= 10
    assert "polarized" in res["verdict"]
    assert res["gray_zone_warning"] is False


def test_polarization_flags_gray_zone():
    # Mostly threshold work → gray-zone warning.
    p = np.concatenate([np.full(3000, 150.0), np.full(7000, 215.0)])  # 215 in 0.75–1.0·250
    res = Z.polarization(p, ftp_w=250.0)
    assert res["gray_zone_warning"] is True
