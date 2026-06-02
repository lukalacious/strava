-- Activity index: identity + summary, one row per activity.
CREATE TABLE IF NOT EXISTS activities (
    activity_id     TEXT PRIMARY KEY,
    sport           TEXT NOT NULL,
    start_time      TEXT NOT NULL,          -- ISO 8601
    name            TEXT,
    distance_m      REAL,
    elapsed_time_s  REAL,
    moving_time_s   REAL,
    total_ascent_m  REAL,
    source          TEXT NOT NULL DEFAULT 'export'
);

-- Write-once derived metrics, keyed by activity_id. Presence == already reduced.
CREATE TABLE IF NOT EXISTS derived_metrics (
    activity_id              TEXT PRIMARY KEY REFERENCES activities(activity_id),
    sport                    TEXT NOT NULL,
    date                     TEXT NOT NULL,  -- local ISO date; the PMC bucket
    duration_s               REAL,
    np_w                     REAL,
    if_                      REAL,
    tss                      REAL,
    avg_power_w              REAL,
    ef                       REAL,
    ngp_ms                   REAL,
    rtss                     REAL,
    avg_speed_ms             REAL,
    avg_hr_bpm               REAL,
    decoupling_pct           REAL,
    ftp_w_used               REAL,
    threshold_pace_ms_used   REAL,
    mmp_json                 TEXT DEFAULT '{}',
    zone_time_json           TEXT DEFAULT '{}',
    ef_series_json           TEXT DEFAULT '[]',
    computed_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_derived_date ON derived_metrics(date);
CREATE INDEX IF NOT EXISTS idx_derived_sport ON derived_metrics(sport);

-- Threshold history: FTP (W) and threshold pace (m/s) as dated time series.
CREATE TABLE IF NOT EXISTS thresholds (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT NOT NULL,
    kind    TEXT NOT NULL,                  -- 'ftp_w' | 'threshold_pace_ms'
    value   REAL NOT NULL,
    method  TEXT NOT NULL                   -- 'auto:...' | 'manual'
);
CREATE INDEX IF NOT EXISTS idx_threshold_kind_date ON thresholds(kind, date);
