#!/usr/bin/env python3
"""Bundled mock Strava MCP server.

This is a small Model Context Protocol (MCP) server that speaks the *real* MCP
protocol over stdio, but serves deterministic, synthetic Strava data instead of
calling the live Strava API. Its purpose is to let the dashboard notebook run
end-to-end (and to let you develop against a stable dataset) without needing a
Strava subscription, OAuth credentials, or network access.

The tool surface intentionally mirrors the shape of community/official Strava
MCP servers (activity lists, per-stream samples, athlete stats, HR zones) so the
notebook's MCP client code is identical whether it is talking to this mock or to
a real server such as ``@r-huijts/strava-mcp-server``.

To use a real server instead, set the ``STRAVA_MCP_COMMAND`` environment
variable (see ``strava_mcp_client.py``).

Run directly with::

    python mock_strava_mcp_server.py
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

# Deterministic dataset: a fixed seed means every run produces the same numbers,
# so the notebook's charts and "personal bests" are stable and reproducible.
SEED = 20260601
DAYS_OF_HISTORY = 480  # ~16 months, enough for year-over-year comparisons.

mcp = FastMCP("mock-strava")


# --------------------------------------------------------------------------- #
# Synthetic data generation
# --------------------------------------------------------------------------- #
def _seasonal_factor(day_of_year: int) -> float:
    """Return a 0.55..1.0 multiplier peaking in mid-summer (northern hemisphere)."""
    # Peak around day 200 (mid/late July), trough in winter.
    phase = math.cos((day_of_year - 200) / 365.0 * 2 * math.pi)
    return 0.55 + 0.45 * (0.5 * (1 - phase))  # maps cos[-1,1] -> [0.55, 1.0]


def _build_activities() -> list[dict[str, Any]]:
    """Generate a deterministic list of synthetic activities."""
    rng = random.Random(SEED)
    activities: list[dict[str, Any]] = []
    start = datetime.now(timezone.utc) - timedelta(days=DAYS_OF_HISTORY)
    activity_id = 15_000_000_000

    # Athlete fitness drifts upward slowly over the history window.
    fitness = 0.0

    for offset in range(DAYS_OF_HISTORY + 1):
        day = start + timedelta(days=offset)
        dow = day.weekday()  # 0 = Mon
        season = _seasonal_factor(day.timetuple().tm_yday)
        fitness = min(1.0, fitness + 0.0015)  # gentle long-term improvement

        # Probability of training on a given day, higher Tue/Thu/Sat/Sun.
        base_p = {0: 0.35, 1: 0.65, 2: 0.45, 3: 0.65, 4: 0.30, 5: 0.80, 6: 0.75}[dow]
        if rng.random() > base_p * (0.6 + 0.4 * season):
            continue

        is_long = dow in (5, 6) and rng.random() < 0.5
        is_ride = rng.random() < 0.62
        activity_id += rng.randint(1, 5)

        if is_ride:
            base_km = (60 if is_long else 32) * season * (0.8 + 0.4 * rng.random())
            distance_km = max(12.0, base_km + rng.gauss(0, 6))
            speed_kmh = 24 + 8 * fitness + (3 if not is_long else -1) + rng.gauss(0, 1.5)
            speed_kmh = max(16.0, speed_kmh)
            moving_time = distance_km / speed_kmh * 3600.0
            elev = distance_km * rng.uniform(6, 14) * (1.4 if is_long else 1.0)
            avg_hr = 128 + 18 * (1 - season * 0.3) + (8 if not is_long else 0) + rng.gauss(0, 5)
            avg_watts = 150 + 70 * fitness + (25 if not is_long else 0) + rng.gauss(0, 12)
            kj = avg_watts * moving_time / 1000.0
            name = rng.choice(
                ["Morning Ride", "Lunch Ride", "Evening Ride", "Weekend Long Ride",
                 "Hill Repeats", "Tempo Ride", "Recovery Spin", "Club Ride"]
            )
            sport = "Ride"
        else:
            base_km = (16 if is_long else 8) * (0.7 + 0.3 * season) * (0.85 + 0.3 * rng.random())
            distance_km = max(3.0, base_km + rng.gauss(0, 1.5))
            pace_min_km = 6.1 - 1.3 * fitness + (0.5 if is_long else -0.2) + rng.gauss(0, 0.25)
            pace_min_km = max(3.9, pace_min_km)
            speed_kmh = 60.0 / pace_min_km
            moving_time = distance_km / speed_kmh * 3600.0
            elev = distance_km * rng.uniform(4, 11)
            avg_hr = 142 + 14 * (1 - season * 0.2) + (10 if not is_long else 2) + rng.gauss(0, 5)
            avg_watts = None
            kj = None
            name = rng.choice(
                ["Morning Run", "Easy Run", "Tempo Run", "Long Run",
                 "Interval Session", "Recovery Jog", "Trail Run", "Parkrun"]
            )
            sport = "Run"

        avg_hr = float(max(95, min(182, avg_hr)))
        max_hr = float(min(196, avg_hr + rng.uniform(12, 26)))
        avg_speed_ms = (distance_km * 1000.0) / moving_time
        elapsed = moving_time * rng.uniform(1.02, 1.18)
        suffer = max(5, (avg_hr - 100) * (moving_time / 3600.0) * rng.uniform(2.0, 3.2))

        # Start time of day: mornings on weekdays, later on weekends.
        hour = rng.choice([6, 7, 7, 8, 17, 18, 19]) if dow < 5 else rng.choice([8, 9, 9, 10, 14])
        start_dt = day.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0)

        activities.append(
            {
                "id": activity_id,
                "name": name,
                "type": sport,
                "sport_type": sport,
                "start_date": start_dt.isoformat().replace("+00:00", "Z"),
                "start_date_local": start_dt.isoformat().replace("+00:00", "Z"),
                "distance": round(distance_km * 1000.0, 1),          # metres
                "moving_time": int(moving_time),                     # seconds
                "elapsed_time": int(elapsed),                        # seconds
                "total_elevation_gain": round(elev, 1),              # metres
                "average_speed": round(avg_speed_ms, 3),             # m/s
                "max_speed": round(avg_speed_ms * rng.uniform(1.4, 2.1), 3),
                "average_heartrate": round(avg_hr, 1),
                "max_heartrate": round(max_hr, 1),
                "average_watts": round(avg_watts, 1) if avg_watts else None,
                "kilojoules": round(kj, 1) if kj else None,
                "average_cadence": round(rng.uniform(78, 94), 1),
                "suffer_score": int(suffer),
                "achievement_count": rng.randint(0, 6),
                "pr_count": rng.randint(0, 3),
            }
        )

    return activities


# Generated once at import; deterministic.
_ACTIVITIES: list[dict[str, Any]] = _build_activities()
_ACTIVITIES_BY_ID = {a["id"]: a for a in _ACTIVITIES}


def _build_streams(activity: dict[str, Any]) -> dict[str, list[float]]:
    """Synthesize per-sample streams for one activity (5 s sampling, capped)."""
    rng = random.Random(activity["id"])
    moving = activity["moving_time"]
    n = min(int(moving // 5), 1440)  # cap at 2 h of 5 s samples for payload size
    n = max(n, 10)
    avg_hr = activity["average_heartrate"]
    max_hr = activity["max_heartrate"]
    avg_v = activity["average_speed"]
    elev_total = activity["total_elevation_gain"]
    avg_w = activity.get("average_watts")

    time_s, hr, velocity, altitude, watts = [], [], [], [], []
    alt = rng.uniform(0, 50)
    hr_state = avg_hr * 0.9
    for i in range(n):
        frac = i / n
        # HR drifts up over the activity and responds to surges.
        target = avg_hr + (max_hr - avg_hr) * (0.3 + 0.5 * frac) * (0.6 + 0.8 * rng.random() ** 3)
        hr_state += (target - hr_state) * 0.08
        hr_val = max(90.0, min(max_hr, hr_state + rng.gauss(0, 2)))
        v = max(0.0, avg_v * (0.8 + 0.4 * rng.random()) + rng.gauss(0, avg_v * 0.1))
        alt += rng.gauss(0, elev_total / max(n, 1) ** 0.5 * 0.4)
        alt = max(0.0, alt)
        time_s.append(i * 5)
        hr.append(round(hr_val, 1))
        velocity.append(round(v, 3))
        altitude.append(round(alt, 1))
        if avg_w:
            watts.append(round(max(0.0, avg_w * (0.7 + 0.6 * rng.random()) + rng.gauss(0, avg_w * 0.15)), 1))

    streams = {
        "time": time_s,
        "heartrate": hr,
        "velocity_smooth": velocity,
        "altitude": altitude,
    }
    if watts:
        streams["watts"] = watts
    return streams


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_recent_activities(per_page: int = 200, days: int | None = None) -> dict[str, Any]:
    """Return the athlete's recent activities (most recent first).

    Args:
        per_page: Maximum number of activities to return.
        days: If set, only include activities within the last ``days`` days.
    """
    items = sorted(_ACTIVITIES, key=lambda a: a["start_date"], reverse=True)
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        items = [a for a in items if datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")) >= cutoff]
    return {"count": len(items[:per_page]), "activities": items[:per_page]}


@mcp.tool()
def get_activity_streams(activity_id: int) -> dict[str, Any]:
    """Return per-sample data streams (time, heartrate, velocity, altitude, watts)."""
    activity = _ACTIVITIES_BY_ID.get(int(activity_id))
    if activity is None:
        return {"error": f"Unknown activity_id {activity_id}"}
    return {"activity_id": activity_id, "streams": _build_streams(activity)}


@mcp.tool()
def get_athlete_stats() -> dict[str, Any]:
    """Return recent / year-to-date / all-time totals for rides and runs."""
    now = datetime.now(timezone.utc)
    ytd = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    recent_cut = now - timedelta(days=28)

    def totals(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "distance": round(sum(a["distance"] for a in items), 1),
            "moving_time": int(sum(a["moving_time"] for a in items)),
            "elevation_gain": round(sum(a["total_elevation_gain"] for a in items), 1),
        }

    def by_type(items: list[dict[str, Any]], sport: str) -> list[dict[str, Any]]:
        return [a for a in items if a["type"] == sport]

    def parse(a: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(a["start_date"].replace("Z", "+00:00"))

    ytd_items = [a for a in _ACTIVITIES if parse(a) >= ytd]
    recent_items = [a for a in _ACTIVITIES if parse(a) >= recent_cut]
    return {
        "recent_ride_totals": totals(by_type(recent_items, "Ride")),
        "recent_run_totals": totals(by_type(recent_items, "Run")),
        "ytd_ride_totals": totals(by_type(ytd_items, "Ride")),
        "ytd_run_totals": totals(by_type(ytd_items, "Run")),
        "all_ride_totals": totals(by_type(_ACTIVITIES, "Ride")),
        "all_run_totals": totals(by_type(_ACTIVITIES, "Run")),
    }


@mcp.tool()
def get_athlete_zones() -> dict[str, Any]:
    """Return the athlete's configured heart-rate zones (bpm boundaries)."""
    return {
        "heart_rate": {
            "custom_zones": False,
            "zones": [
                {"name": "Z1 Endurance", "min": 0, "max": 123},
                {"name": "Z2 Moderate", "min": 123, "max": 142},
                {"name": "Z3 Tempo", "min": 142, "max": 158},
                {"name": "Z4 Threshold", "min": 158, "max": 173},
                {"name": "Z5 Anaerobic", "min": 173, "max": -1},
            ],
        }
    }


if __name__ == "__main__":
    mcp.run()
