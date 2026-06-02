"""BLOCKING regression fixture — the Vaujany ride.

The compute layer must reproduce the known numbers below off the real `.fit`
before any longitudinal output is trusted. Drop the file at one of:

    backend/data/raw/vaujany.fit
    backend/data/raw/vaujany.fit.gz

(or set TRAININGDASH_VAUJANY_FIT to its path). Until then this test SKIPS with
instructions rather than silently passing.

If the pipeline doesn't land these numbers, the math is wrong — fix it before
building anything on top.
"""
import os
from pathlib import Path

import numpy as np
import pytest

from trainingdash.compute import decoupling, power
from trainingdash.ingest.fit import parse_fit

# (expected value, absolute tolerance)
EXPECTED = {
    "distance_km": (185.2, 2.0),
    "ascent_m": (5019, 150),
    "np_w": (189, 5),
    "if_": (0.78, 0.03),
    "tss": (527, 20),
    "ftp_w": (243, 8),
    "cp_w": (204, 12),
    "wprime_kj": (63.1, 10),
    "decoupling_pct": (3.3, 1.5),
}


def _find_fit() -> Path | None:
    env = os.environ.get("TRAININGDASH_VAUJANY_FIT")
    if env and Path(env).exists():
        return Path(env)
    raw = Path(__file__).resolve().parents[1] / "data" / "raw"
    for name in ("vaujany.fit", "vaujany.fit.gz"):
        if (raw / name).exists():
            return raw / name
    hits = list(raw.glob("*aujany*.fit*")) if raw.exists() else []
    return hits[0] if hits else None


@pytest.fixture(scope="module")
def vaujany():
    path = _find_fit()
    if path is None:
        pytest.skip(
            "Vaujany .fit not found. Drop it at backend/data/raw/vaujany.fit "
            "(or set TRAININGDASH_VAUJANY_FIT) to run the blocking regression."
        )
    return parse_fit(path, activity_id="vaujany")


def _check(name, value):
    exp, tol = EXPECTED[name]
    assert value == pytest.approx(exp, abs=tol), f"{name}: got {value}, expected {exp}±{tol}"


def test_vaujany_summary(vaujany):
    summary, streams = vaujany
    _check("distance_km", summary.distance_m / 1000.0)
    _check("ascent_m", summary.total_ascent_m)


def test_vaujany_power_metrics(vaujany):
    summary, streams = vaujany
    sr = streams.sample_rate_hz
    np_w = power.normalized_power(streams.power_w, sr)
    ftp = 0.95 * power.mean_maximal_power(streams.power_w, 1200, sr)
    moving_s = float(streams.moving_mask().sum() / sr)
    _check("np_w", np_w)
    _check("ftp_w", ftp)
    _check("if_", power.intensity_factor(np_w, ftp))
    _check("tss", power.tss(moving_s, np_w, ftp))


def test_vaujany_cp_wprime(vaujany):
    summary, streams = vaujany
    cp, wprime = power.estimate_cp_wprime_from_streams(streams.power_w, sample_rate_hz=streams.sample_rate_hz)
    _check("cp_w", cp)
    _check("wprime_kj", wprime / 1000.0)


def test_vaujany_decoupling(vaujany):
    summary, streams = vaujany
    moving = streams.moving_mask()
    dec = decoupling.decoupling_pct(streams.power_w, streams.hr_bpm, mask=moving, min_output=50)
    _check("decoupling_pct", dec)
