# trainingdash — compute layer

A multi-sport (cycling + running) longitudinal training dashboard. This backend
is a **compute layer over raw per-second streams**, not a skin over Strava's
scores. Fitness/fatigue/form over time, with full-depth single-session drill-down.

## Non-negotiables (honored)

1. **Everything computed from raw streams.** NP, IF, TSS, FTP, CP, W′, EF,
   decoupling, NGP, rTSS, zones, CTL/ATL/TSB — all derived here from per-second
   data + a stored threshold. Strava's Fitness / Relative Effort / Readiness
   never enter the data model.
2. **Metric units throughout** (W, km, m, °C, bpm, min/km, m/s internally).
3. **Reproducible & testable.** Every metric recomputes from a stored stream +
   a stored, dated threshold. 36 unit tests with analytically-derived expected
   values; a blocking regression fixture for the Vaujany ride.

## Architecture

```
Strava bulk export (.fit)  ─┐
                            ├─► ingest (canonical 1 Hz Streams) ─► reduce ─► SQLite cache
Strava MCP (incremental)  ──┘                                                 + NPZ stream cache
                                                                                   │
                                          PMC / power-curve / durability / panels ─┘
```

- `trainingdash/models.py` — `Streams` (1 Hz canonical), `ActivitySummary`,
  `DerivedMetrics`, `ThresholdPoint`.
- `trainingdash/compute/` — pure metric functions:
  - `power.py` — NP, IF, TSS, mean-maximal power, CP/W′ (Monod–Scherrer), EF, EF/hour.
  - `running.py` — Minetti GAP, NGP, rTSS.
  - `decoupling.py` — Pw:Hr / Pa:Hr aerobic decoupling.
  - `zones.py` — Coggan power zones, HR zones, 80/20 polarization + gray-zone warning.
  - `pmc.py` — unified daily load (with tunable `rtss_scale`), CTL/ATL/TSB EWMA,
    ramp rate, form band + verdict.
  - `thresholds.py` — FTP / threshold-pace auto-detection from the MMP curve.
- `trainingdash/ingest/` — `.fit` parser (`fitparse`) + 1 Hz canonicalizer.
- `trainingdash/store/` — SQLite (activities, write-once `derived_metrics`,
  dated `thresholds`) + on-disk NPZ stream cache.
- `trainingdash/pipeline.py` — idempotent ingest→reduce→cache; PMC build.
- `trainingdash/cli.py` — `ingest-export`, `pmc`.

## Modeling decisions (as specified)

- **Unified PMC** — bike TSS + run rTSS into one load/CTL/ATL/TSB, with a single
  tunable `rtss_scale` for cross-sport recalibration.
- **FTP & threshold pace are dated time series** — auto-detected, stored as
  history, manual override wins on a given date (`Store.effective_threshold`).
- **HRmax is an editable input**, never a buried constant (HR zones take explicit
  edges; nothing assumes 190).

## Run it

```bash
pip install -r requirements-backend.txt

# 1. Backfill from a Strava bulk export (one-time, no rate limits)
python -m trainingdash.cli ingest-export /path/to/strava_export --db data/cache.sqlite

# 2. Inspect current form
python -m trainingdash.cli pmc --db data/cache.sqlite --rtss-scale 1.0

# Tests (run from backend/)
python -m pytest -q
```

## Blocking regression fixture

Before trusting any longitudinal output, the pipeline must reproduce the known
Vaujany ride. Drop the file at `backend/data/raw/vaujany.fit` (or set
`TRAININGDASH_VAUJANY_FIT`) and run `pytest`. Targets: 185.2 km / 5019 m / NP 189 W
/ IF 0.78 / TSS 527 / FTP 243 W / CP 204 W / W′ 63.1 kJ / decoupling 3.3%.
Until the file is present these 4 tests **skip with instructions** (they do not
silently pass).

## Build status

| Step | Status |
|------|--------|
| 1. Ingest + reduce + cache | ✅ done (`.fit` + SQLite + NPZ, write-once, idempotent) |
| 2. PMC (load → CTL/ATL/TSB → ramp → form) | ✅ done |
| 3. Power curve + FTP/CP history | ✅ compute + store done; chart endpoint pending |
| 4. Durability (decoupling, EF, late-effort retention) | ✅ metrics done; panel pending |
| 5. Distribution / polarization | ✅ compute done; panel pending |
| 6. Session drill-down | ✅ stream cache + per-activity metrics; UI pending |
| 7. MCP wiring (incremental + conversational) | ⏳ last, as specified |
| FastAPI endpoints + React/Recharts front end | ⏳ next |

The compute foundation is complete and tested. Remaining work is the HTTP API
(FastAPI over the store) and the React/Recharts panels (telemetry/instrument
aesthetic, dark, monospace numerics), then MCP incremental ingest.

## Day-one verification (resolved)

Confirmed Strava's official MCP exposes **raw per-second streams** via
`get_activity_streams` (HR, pace, power, cadence). So the MCP can serve
incremental stream ingestion; it is not demoted to conversational-only. Bulk
export remains the historical backfill source.
