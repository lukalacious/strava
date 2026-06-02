# Strava Tell Me More 🚴‍♂️ (archived)

> **This is an earlier project, archived here.** The repository's current focus
> is the **Strava Performance & Training Dashboard** — see the
> [root README](../README.md). These files are preserved for reference.

A Python notebook that integrates with the Strava API and OpenAI to generate
engaging historical stories about your real cycling routes through Dutch cities
and towns.

## Features

### 🚴‍♂️ Real Strava Integration
- Connects to your Strava account to fetch real cycling activities
- Extracts GPS route data from your actual rides
- Processes coordinates into location waypoints
- Falls back gracefully to mock data when Strava API is unavailable

### 🤖 AI-Powered Storytelling
- Generates engaging historical narratives using OpenAI's GPT models
- Multiple story types: Dutch Golden Age, Modern, WWII Liberation themes
- Immersive storytelling that makes you feel like you were there
- Individual city summaries for deeper historical context

### 📊 Smart Data Processing
- Modular architecture with separate classes for different functions
- GPS coordinate processing and location extraction
- Intelligent fallback systems for robustness
- JSON output with metadata for story archival

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r ../requirements.txt
   ```

2. **Get API Keys:**

   **OpenAI API Key:** Sign up at [OpenAI](https://platform.openai.com/) and
   create an API key.

   **Strava API Credentials (optional but recommended):** Create an application
   at [Strava API Settings](https://www.strava.com/settings/api) to get a Client
   ID and Client Secret, then generate an access token.

3. **Configure environment variables:** copy `../.env.template` to `../.env` and
   fill in your keys:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   STRAVA_CLIENT_ID=your_strava_client_id_here
   STRAVA_CLIENT_SECRET=your_strava_client_secret_here
   STRAVA_ACCESS_TOKEN=your_strava_access_token_here
   ```

## Usage

```bash
jupyter notebook "legacy/strava_tell_me_more (strava-api).ipynb"
```

Run all cells; the notebook will connect to Strava (if configured), fetch recent
activities, extract route waypoints from GPS data, and generate historical
stories, saving them as JSON files.

### Story Types Generated
- **Golden Age** — your route as if cycling through 17th-century Netherlands
- **Modern** — contemporary cycling with historical context
- **War Liberation** — WWII liberation perspective (1944–1945)

### Fallback Mode
If the Strava API isn't configured, the notebook uses mock Dutch cycling route
data (Segbroek, Kraayenstein, Kwintsheul, Schipluiden, Berkel en Rodenrijs,
Pijnacker, Leidschendam, Marlot, Haagse Bos).

## Architecture

- **StravaAPI** — Strava authentication and data fetching
- **RouteProcessor** — converts GPS coordinates to location names
- **StoryGenerator** — creates AI-powered historical narratives
- **CityHistoryGenerator** (`city_history_generator.py`) — standalone city
  history generator; see `example_usage.py` for programmatic examples

## Files

| File | Description |
|------|-------------|
| `strava_tell_me_more (strava-api).ipynb` | Main notebook with live Strava integration |
| `strava_tell_me_more.ipynb` / `_CLEAN.ipynb` | Earlier / cleaned variants |
| `strava_tell_me_more (pre-api).ipynb` | Pre-API prototype |
| `city_history_generator.py` / `.ipynb` | City history generator |
| `example_usage.py` | Programmatic usage examples |

## License

Open source under the MIT License (see [../LICENSE](../LICENSE)).
