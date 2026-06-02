# 🚴‍♂️ Strava Performance & Training Dashboard

An analytics dashboard for your Strava data — **training trends** and
**performance & efforts** — powered by a **Strava MCP (Model Context Protocol)
server**.

The dashboard notebook acts as an **MCP client**: it launches a Strava MCP
server over stdio, discovers its tools at runtime, and pulls the results into
pandas for analysis and charts. It ships with a bundled mock MCP server so it
runs end-to-end with realistic synthetic data and **no credentials**, then
switches to your real data by setting a single environment variable.

> ℹ️ This repository previously hosted a different project ("Strava Tell Me
> More", an AI story generator). That project is archived under
> [`legacy/`](legacy/README.md).

## What it analyses

**Training trends**
- Weekly distance & training time (with 4-week rolling average)
- Monthly totals and elevation
- Year-over-year cumulative distance
- Consistency: activities per week and day-of-week patterns

**Performance & efforts**
- Pace (runs) and speed (rides) distributions
- Heart-rate-zone distribution (time in each zone)
- Aerobic efficiency (speed-per-HR) trend over time — a fitness indicator
- Training load with the **Acute:Chronic Workload Ratio (ACWR)** injury-risk band
- Personal bests / top efforts
- Single-activity drill-down from per-second **streams** (HR, speed, time-in-zone)

## Architecture

```
strava_dashboard.ipynb  ──(MCP client)──►  Strava MCP server  ──►  your activity data
       │                                          ▲
       │ default (no creds)                       │ STRAVA_MCP_COMMAND set
       └──────────────►  mock_strava_mcp_server.py (bundled, synthetic data)
```

The **same client code** talks to either server. Tools are matched by capability
and fields are normalised with tolerant aliases, so the dashboard works with the
bundled mock, with [`@r-huijts/strava-mcp-server`](https://github.com/r-huijts/strava-mcp),
or with other Strava MCP servers that name things differently.

| File | Description |
|------|-------------|
| `notebooks/strava_dashboard.ipynb` | The dashboard (run this) |
| `notebooks/strava_mcp_client.py` | MCP client + Strava adapter (tool discovery, normalisation) |
| `notebooks/mock_strava_mcp_server.py` | Bundled MCP server serving deterministic synthetic data |

## Quick start

```bash
pip install -r requirements.txt
jupyter notebook notebooks/strava_dashboard.ipynb   # then "Run All"
```

With no configuration the dashboard uses the **bundled mock server** — great for
trying it out or developing against stable data.

## Use your own Strava data

Point the client at a real Strava MCP server and provide your Strava
credentials. Copy `.env.template` to `.env` and set:

```bash
STRAVA_MCP_COMMAND="npx -y @r-huijts/strava-mcp-server"
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_ACCESS_TOKEN=...
STRAVA_REFRESH_TOKEN=...
```

Get credentials by creating an app at
[Strava API Settings](https://www.strava.com/settings/api) and authorising with
the `read,activity:read` scopes.

> **Note on Strava's official MCP Connector.** Strava's official MCP (launched
> June 2026) is a **remote, OAuth-based, Claude-only** subscription feature for
> *conversational* access — there is no public programmatic local endpoint a
> notebook can drive. For a self-contained dashboard, a local stdio MCP server
> (like the one above) is the practical data source; swap `STRAVA_MCP_COMMAND`
> if/when a local bridge to the official connector becomes available.

## Requirements

- Python 3.9+
- Node.js (only if you use an `npx`-based MCP server for live data)
- See `requirements.txt` (`mcp`, `pandas`, `matplotlib`, `nest-asyncio`, …)

## Legacy project

The earlier "Strava Tell Me More" AI story generator lives in
[`legacy/`](legacy/README.md) and is kept for reference.

## License

Open source under the [MIT License](LICENSE).
