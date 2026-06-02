#!/usr/bin/env python3
"""Strava MCP client for the analysis dashboard.

This module connects to a Strava **Model Context Protocol (MCP)** server over
stdio and normalises the tool output into tidy :class:`pandas.DataFrame`
objects that the dashboard notebook can analyse.

The exact same client code works against:

* the bundled :mod:`mock_strava_mcp_server` (the default — synthetic data, no
  credentials needed), and
* a real Strava MCP server such as ``@r-huijts/strava-mcp-server`` (set the
  ``STRAVA_MCP_COMMAND`` environment variable, below).

Because different Strava MCP servers name their tools and shape their JSON
slightly differently, the client *discovers* the available tools at runtime,
matches them by keyword, and normalises records using a tolerant set of field
aliases. That keeps the notebook decoupled from any single server.

Configuration (environment variables)
--------------------------------------
``STRAVA_MCP_COMMAND``
    Full command used to launch the MCP server, e.g.
    ``npx -y @r-huijts/strava-mcp-server``. If unset, the bundled mock server is
    launched with the current Python interpreter.
``STRAVA_CLIENT_ID`` / ``STRAVA_CLIENT_SECRET`` / ``STRAVA_ACCESS_TOKEN`` /
``STRAVA_REFRESH_TOKEN``
    Forwarded to the server process so a real server can authenticate. Ignored
    by the mock server.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

import nest_asyncio
import numpy as np
import pandas as pd

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Allow the asyncio-based MCP client to run inside an already-running Jupyter
# event loop.
nest_asyncio.apply()

_THIS_DIR = Path(__file__).resolve().parent
_FORWARDED_ENV_KEYS = (
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "STRAVA_ACCESS_TOKEN",
    "STRAVA_REFRESH_TOKEN",
    "ROUTE_EXPORT_PATH",
)

# Field aliases: canonical column name -> possible keys in a server's JSON.
_ACTIVITY_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "activity_id"),
    "name": ("name", "title"),
    "type": ("type", "sport_type", "sport"),
    "start_date": ("start_date", "start_date_local", "startDate", "start"),
    "distance_m": ("distance", "distance_m", "distance_meters"),
    "moving_time_s": ("moving_time", "moving_time_s", "movingTime"),
    "elapsed_time_s": ("elapsed_time", "elapsed_time_s", "elapsedTime"),
    "elevation_gain_m": ("total_elevation_gain", "elevation_gain", "elev_gain"),
    "average_speed_ms": ("average_speed", "avg_speed", "averageSpeed"),
    "max_speed_ms": ("max_speed", "maxSpeed"),
    "average_hr": ("average_heartrate", "avg_hr", "averageHeartrate", "average_heart_rate"),
    "max_hr": ("max_heartrate", "max_hr", "maxHeartrate"),
    "average_watts": ("average_watts", "avg_watts", "averageWatts"),
    "kilojoules": ("kilojoules", "kj"),
    "average_cadence": ("average_cadence", "avg_cadence"),
    "suffer_score": ("suffer_score", "relative_effort", "sufferScore"),
    "achievement_count": ("achievement_count",),
    "pr_count": ("pr_count",),
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _run(coro):
    """Run an async coroutine to completion from sync code (Jupyter-safe)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _first(record: dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in record and record[k] is not None:
            return record[k]
    return None


def _extract_payload(result) -> Any:
    """Turn an MCP CallToolResult into a Python object.

    Prefers ``structuredContent``; otherwise concatenates text content blocks
    and attempts to JSON-decode them.
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        # FastMCP wraps non-dict returns under a "result" key.
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    texts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    blob = "\n".join(texts).strip()
    if not blob:
        return None
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, ValueError):
        return blob


def _find_list(payload: Any, prefer: tuple[str, ...] = ("activities", "data", "results", "items")) -> list:
    """Find the list of records inside a server payload of unknown shape."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in prefer:
            if isinstance(payload.get(key), list):
                return payload[key]
        for value in payload.values():  # fall back to first list-valued field
            if isinstance(value, list):
                return value
    return []


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class StravaMCPClient:
    """Connects to a Strava MCP server and returns normalised DataFrames."""

    def __init__(self, command: Optional[str] = None, verbose: bool = True):
        self.verbose = verbose
        self._server_params = self._resolve_server(command)
        self.tool_names: list[str] = []

    # -- connection / discovery -------------------------------------------- #
    def _resolve_server(self, command: Optional[str]) -> StdioServerParameters:
        command = command or os.getenv("STRAVA_MCP_COMMAND", "").strip()
        # Forward the full parent environment so launchers like `npx`/`node`
        # find their tooling (npm cache, NODE_PATH, etc.), then ensure the
        # Strava credentials are present even if absent from the parent.
        env = dict(os.environ)
        for key in _FORWARDED_ENV_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value

        if command:
            parts = shlex.split(command)
            if self.verbose:
                print(f"🔌 Strava MCP server: {command}")
            return StdioServerParameters(command=parts[0], args=parts[1:], env=env)

        mock = _THIS_DIR / "mock_strava_mcp_server.py"
        if self.verbose:
            print(f"🔌 Strava MCP server: bundled mock ({mock.name})")
            print("   (set STRAVA_MCP_COMMAND to point at a live server, e.g. "
                  "'npx -y @r-huijts/strava-mcp-server')")
        return StdioServerParameters(command=sys.executable, args=[str(mock)], env=env)

    async def _session(self):
        """Async context returning an initialised ClientSession (internal)."""
        # Used via the gather-style helpers below.
        raise NotImplementedError  # pragma: no cover

    async def _with_session(self, work):
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                self.tool_names = [t.name for t in listed.tools]
                return await work(session, listed.tools)

    def list_tools(self) -> list[str]:
        """Return the tool names advertised by the connected server."""
        async def work(session, tools):
            return [t.name for t in tools]
        return _run(self._with_session(work))

    # -- tool matching ----------------------------------------------------- #
    @staticmethod
    def _match_tool(
        tools,
        must: tuple[str, ...],
        avoid: tuple[str, ...] = (),
        prefer: tuple[str, ...] = (),
    ) -> Optional[Any]:
        """Pick the best-matching tool by name.

        A tool is a candidate only if its name contains every term in ``must``
        and none in ``avoid``. Among candidates, names containing ``prefer``
        terms score higher (useful when a server exposes several similarly
        named tools, e.g. preferring a *list* endpoint over a *details* one),
        with shorter / more generic names breaking ties.
        """
        best, best_score = None, float("-inf")
        for tool in tools:
            name = tool.name.lower()
            if any(a in name for a in avoid):
                continue
            if not all(m in name for m in must):
                continue
            score = len(must) + sum(0.5 for p in prefer if p in name)
            score -= len(name) * 0.001  # tie-break toward shorter names
            if score > best_score:
                best, best_score = tool, score
        return best

    @staticmethod
    def _supported_args(tool, desired: dict[str, Any]) -> dict[str, Any]:
        """Keep only arguments the tool's input schema actually declares."""
        schema = getattr(tool, "inputSchema", None) or {}
        props = set((schema.get("properties") or {}).keys())
        if not props:
            return {}
        return {k: v for k, v in desired.items() if k in props}

    # -- high-level fetches ------------------------------------------------ #
    def fetch_activities(self, limit: int = 200, days: Optional[int] = None) -> pd.DataFrame:
        """Fetch activities and return a normalised DataFrame."""
        async def work(session, tools):
            tool = self._match_tool(
                tools,
                ("activit",),
                avoid=("stream", "stats", "zone", "lap", "detail", "comment", "kudo", "photo"),
                prefer=("activities", "recent", "list", "fetch", "all"),
            )
            if tool is None:
                raise RuntimeError(
                    f"No activities tool found. Available tools: {[t.name for t in tools]}"
                )
            args = self._supported_args(
                tool, {"per_page": limit, "limit": limit, "count": limit, "days": days}
            )
            if self.verbose:
                print(f"📥 calling tool '{tool.name}' args={args}")
            result = await session.call_tool(tool.name, args)
            return _extract_payload(result)

        payload = _run(self._with_session(work))
        records = _find_list(payload)
        return self._normalise_activities(records)

    def fetch_streams(self, activity_id: int) -> pd.DataFrame:
        """Fetch per-sample streams for one activity as a DataFrame."""
        async def work(session, tools):
            tool = self._match_tool(tools, ("stream",))
            if tool is None:
                raise RuntimeError("No streams tool found on this server.")
            args = self._supported_args(
                tool, {"activity_id": activity_id, "id": activity_id, "activityId": activity_id}
            )
            result = await session.call_tool(tool.name, args)
            return _extract_payload(result)

        payload = _run(self._with_session(work))
        streams = payload.get("streams", payload) if isinstance(payload, dict) else {}
        if not isinstance(streams, dict):
            return pd.DataFrame()
        # streams may be {name: [..]} or {name: {"data": [..]}}.
        cols = {}
        for name, value in streams.items():
            if isinstance(value, dict) and "data" in value:
                cols[name] = value["data"]
            elif isinstance(value, list):
                cols[name] = value
        max_len = max((len(v) for v in cols.values()), default=0)
        cols = {k: v for k, v in cols.items() if len(v) == max_len}
        return pd.DataFrame(cols)

    def fetch_zones(self) -> Optional[list[dict[str, Any]]]:
        """Fetch heart-rate zone boundaries, if the server exposes them."""
        async def work(session, tools):
            tool = self._match_tool(tools, ("zone",))
            if tool is None:
                return None
            result = await session.call_tool(tool.name, self._supported_args(tool, {}))
            return _extract_payload(result)

        payload = _run(self._with_session(work))
        if not isinstance(payload, dict):
            return None
        hr = payload.get("heart_rate", payload)
        zones = hr.get("zones") if isinstance(hr, dict) else None
        return zones if isinstance(zones, list) else None

    def fetch_stats(self) -> Optional[dict[str, Any]]:
        """Fetch athlete totals (recent / YTD / all-time), if available."""
        async def work(session, tools):
            tool = self._match_tool(tools, ("stats",)) or self._match_tool(tools, ("total",))
            if tool is None:
                return None
            result = await session.call_tool(tool.name, self._supported_args(tool, {}))
            return _extract_payload(result)

        payload = _run(self._with_session(work))
        return payload if isinstance(payload, dict) else None

    # -- normalisation ----------------------------------------------------- #
    @staticmethod
    def _normalise_activities(records: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            rows.append({canon: _first(rec, aliases) for canon, aliases in _ACTIVITY_ALIASES.items()})
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df["start_date"] = pd.to_datetime(df["start_date"], utc=True, errors="coerce")
        numeric = [
            "distance_m", "moving_time_s", "elapsed_time_s", "elevation_gain_m",
            "average_speed_ms", "max_speed_ms", "average_hr", "max_hr",
            "average_watts", "kilojoules", "average_cadence", "suffer_score",
            "achievement_count", "pr_count",
        ]
        for col in numeric:
            df[col] = pd.to_numeric(df.get(col), errors="coerce")

        df = df.dropna(subset=["start_date"]).sort_values("start_date").reset_index(drop=True)
        return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add convenience columns used throughout the dashboard."""
    if df.empty:
        return df
    df = df.copy()
    df["distance_km"] = df["distance_m"] / 1000.0
    df["moving_hours"] = df["moving_time_s"] / 3600.0
    df["moving_minutes"] = df["moving_time_s"] / 60.0
    df["speed_kmh"] = df["average_speed_ms"] * 3.6
    # Pace in minutes per km (guard against divide-by-zero -> inf).
    df["pace_min_km"] = ((df["moving_time_s"] / 60.0) / df["distance_km"]).replace(
        [np.inf, -np.inf], np.nan
    )
    df["date"] = df["start_date"].dt.tz_convert("UTC").dt.date
    df["year"] = df["start_date"].dt.year
    _naive = df["start_date"].dt.tz_localize(None)  # period labels only; drop tz
    df["month"] = _naive.dt.to_period("M").astype(str)
    df["week"] = _naive.dt.to_period("W").astype(str)
    df["dow"] = df["start_date"].dt.dayofweek
    df["dow_name"] = df["start_date"].dt.day_name()
    df["hour"] = df["start_date"].dt.hour
    df["day_of_year"] = df["start_date"].dt.dayofyear
    return df


if __name__ == "__main__":
    # Smoke test: connect to whichever server is configured and summarise.
    client = StravaMCPClient()
    print("tools:", client.list_tools())
    activities = add_derived_columns(client.fetch_activities(limit=500))
    print(f"activities: {len(activities)} rows")
    if not activities.empty:
        print(activities[["start_date", "type", "distance_km", "average_hr"]].tail())
