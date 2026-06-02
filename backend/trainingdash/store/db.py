"""SQLite store: activity index, write-once derived-metric cache, threshold history.

Raw per-second streams are cached separately on disk (NPZ) keyed by activity_id
so the session drill-down never re-pulls or re-reduces a processed activity.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from ..models import ActivitySummary, DerivedMetrics, Streams, ThresholdPoint

_SCHEMA = Path(__file__).with_name("schema.sql")


class Store:
    def __init__(self, db_path: str | Path, streams_dir: str | Path | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.streams_dir = Path(streams_dir) if streams_dir else self.db_path.parent / "streams"
        self.streams_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA.read_text())
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- activities -------------------------------------------------------- #
    def upsert_activity(self, a: ActivitySummary) -> None:
        self.conn.execute(
            """INSERT INTO activities
               (activity_id, sport, start_time, name, distance_m,
                elapsed_time_s, moving_time_s, total_ascent_m, source)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(activity_id) DO UPDATE SET
                 sport=excluded.sport, start_time=excluded.start_time,
                 name=excluded.name, distance_m=excluded.distance_m,
                 elapsed_time_s=excluded.elapsed_time_s,
                 moving_time_s=excluded.moving_time_s,
                 total_ascent_m=excluded.total_ascent_m, source=excluded.source""",
            (a.activity_id, a.sport, a.start_time.isoformat(), a.name, a.distance_m,
             a.elapsed_time_s, a.moving_time_s, a.total_ascent_m, a.source),
        )
        self.conn.commit()

    # -- derived metrics (write-once) -------------------------------------- #
    def is_processed(self, activity_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM derived_metrics WHERE activity_id=?", (activity_id,)
        )
        return cur.fetchone() is not None

    def upsert_derived(self, m: DerivedMetrics) -> None:
        d = asdict(m)
        d["computed_at"] = datetime.utcnow().isoformat()
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        updates = ", ".join(f"{k}=excluded.{k}" for k in d if k != "activity_id")
        self.conn.execute(
            f"INSERT INTO derived_metrics ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(activity_id) DO UPDATE SET {updates}",
            tuple(d.values()),
        )
        self.conn.commit()

    def get_derived(self, activity_id: str) -> Optional[dict]:
        cur = self.conn.execute(
            "SELECT * FROM derived_metrics WHERE activity_id=?", (activity_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def all_derived(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM derived_metrics ORDER BY date")
        return [dict(r) for r in cur.fetchall()]

    # -- thresholds (dated history) ---------------------------------------- #
    def add_threshold(self, t: ThresholdPoint) -> None:
        self.conn.execute(
            "INSERT INTO thresholds (date, kind, value, method) VALUES (?,?,?,?)",
            (t.date, t.kind, t.value, t.method),
        )
        self.conn.commit()

    def effective_threshold(self, kind: str, on_date: str) -> Optional[float]:
        """Most recent threshold value of ``kind`` dated on/before ``on_date``.

        Manual entries on a date win over auto entries on the same date.
        """
        cur = self.conn.execute(
            """SELECT value FROM thresholds
               WHERE kind=? AND date<=?
               ORDER BY date DESC,
                        CASE WHEN method='manual' THEN 0 ELSE 1 END
               LIMIT 1""",
            (kind, on_date),
        )
        row = cur.fetchone()
        return float(row["value"]) if row else None

    def threshold_history(self, kind: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT date, value, method FROM thresholds WHERE kind=? ORDER BY date", (kind,)
        )
        return [dict(r) for r in cur.fetchall()]

    # -- raw stream cache (on disk, write-once) ---------------------------- #
    def _stream_path(self, activity_id: str) -> Path:
        safe = activity_id.replace("/", "_")
        return self.streams_dir / f"{safe}.npz"

    def has_streams(self, activity_id: str) -> bool:
        return self._stream_path(activity_id).exists()

    def save_streams(self, activity_id: str, s: Streams) -> None:
        arrays = {"time_s": np.asarray(s.time_s, dtype="float64")}
        for ch in ("power_w", "hr_bpm", "speed_ms", "altitude_m", "distance_m",
                   "cadence_rpm", "temperature_c"):
            v = getattr(s, ch)
            if v is not None:
                arrays[ch] = np.asarray(v, dtype="float64")
        if s.latlng is not None:
            arrays["latlng"] = np.asarray(s.latlng, dtype="float64")
        np.savez_compressed(self._stream_path(activity_id), **arrays)

    def load_streams(self, activity_id: str) -> Optional[Streams]:
        path = self._stream_path(activity_id)
        if not path.exists():
            return None
        data = np.load(path)
        kwargs = {k: data[k] for k in data.files}
        return Streams(**kwargs)
