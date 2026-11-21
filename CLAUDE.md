# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pflaenzli Backend is a Django REST API that serves as the hub between an Arduino plant-watering device and a Vue frontend. It stores moisture readings and pump actions from the Arduino, provides configuration to it, and exposes all data to the frontend.

## Development Commands

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`). Run `uv sync` once to create the `.venv`, then prefix commands with `uv run` (or activate `.venv`).

```bash
# Create/sync the environment from the lockfile
uv sync

# Run dev server (port 8000)
uv run python manage.py runserver 0.0.0.0:8000

# Run all tests
uv run python manage.py test

# Run a single test class or method
uv run python manage.py test api.tests.StrictQueryParamMixinTests
uv run python manage.py test api.tests.StrictQueryParamMixinTests.test_sensor_unknown_query_param_returns_400

# Apply migrations
uv run python manage.py migrate

# Load initial configuration fixture
uv run python manage.py loaddata configuration

# Run one scheduler tick manually (for debugging; prod cron hits POST /internal/tick)
uv run python manage.py tick
```

Settings come from `.env` (copy `.env.example`). Every variable is required and has no default.

No linting or type-checking tools are configured.

## Architecture

Single Django app (`api`) with Django REST Framework. All URLs are registered via a `DefaultRouter` at `/api/` with `trailing_slash=False`.

### Models

- **MoistureReading** — timestamped soil moisture value (integer)
- **PumpAction** — timestamped pump on/off action (boolean); rows are written when the Arduino reports its real state via `POST /api/pump` (for both manual and scheduled waterings — the manual endpoint and the dispatcher only relay the start command to the Arduino)
- **ScheduledPumpAction** — pump actions for the current day (time only); `fired_at` is the local time the dispatcher fired it (null while pending)
- **Schedule** — one row per planning day (distinct from `ScheduledPumpAction`); snapshots that day's ET0 (`schedule_date`, `et0`). Its existence marks "today already planned"
- **Configuration** — singleton (pk=1) with runtime parameters: `measurement_interval`, `pump_duration`, `valve_duration`, `measurement_enabled`, `pump_enabled`, plus irrigation planning: `pump_seconds_per_mm` (pump runtime in seconds needed per mm of ET0), `calc_time`, `window_start`/`window_end` (the per-event pump runtime reuses `pump_duration`). The location (`LATITUDE`/`LONGITUDE`/`LOCAL_TIMEZONE`) comes from env, not the model

### Irrigation services

Real logic lives in plain service modules, not views: `api/planner.py` (Open-Meteo ET0 fetch + daily plan; `events_for_et0()` converts the day's ET0 into a number of pump events, then writes a `Schedule` row and the spread `ScheduledPumpAction`s), `api/dispatcher.py` (`tick()` — plan if today has no `Schedule`, then fire one pump cycle if any action is due; overdue actions collapse into a single watering and the due actions are marked fired). The tick endpoint and `python manage.py tick` both call `dispatcher.tick()`. The watering time needed is `et0_mm * pump_seconds_per_mm` seconds; `events_for_et0()` divides that by `pump_duration` (the per-event runtime) and rounds up to get the number of pump events.

`api/monitoring.py` (`report()`, called at the end of every tick) pings healthchecks.io at most every `HC_PING_INTERVAL_MINUTES`. It sends the success URL, or `/fail` with a reason when moisture readings are stale (`HC_ARDUINO_STALE_MINUTES`) or the last fired action wasn't confirmed by a pump-on report within `HC_PUMP_CONFIRM_MINUTES`. It must never raise, so a monitoring failure can't break watering. An empty `HEALTHCHECKS_URL` disables it.

### API Endpoints

All endpoints are under `/api/`:

| Route | Purpose |
|---|---|
| `GET/POST /api/sensor` | Moisture readings (filterable by `start`/`end` datetime) |
| `PUT /api/sensor/trigger` | Trigger a measurement on the Arduino |
| `GET/POST /api/pump` | Pump action history (filterable by `start`/`end` datetime) |
| `PUT /api/pump/start` | Start pump on Arduino |
| `PUT /api/pump/stop` | Stop pump on Arduino |
| `GET/PUT /api/configuration/1` | Read/update configuration (also pushes to Arduino on update) |
| `GET /api/configuration/retrieve_from_arduino` | Fetch live config from Arduino |
| `GET/POST/PUT/DELETE /api/scheduled-pump` | Today's pending (unfired) scheduled pump actions (time only) |
| `GET /api/schedule` | Read-only daily `Schedule` rows (ET0 per day; filterable by `start`/`end` date) |
| `POST /internal/tick` | Internal scheduler tick (localhost-only; outside `/api/`) |

### Arduino Communication (`api/actions.py`)

The backend forwards commands to the Arduino via HTTP requests to `settings.ARDUINO_ADDRESS`, with a 5 s timeout (`ARDUINO_TIMEOUT`) so an unreachable Arduino can't hang a gunicorn worker. `ARDUINO_ENABLED=False` (env, independent of `DEBUG`) turns these calls into no-ops so the dev server works without hardware.

### Query Parameter Validation

`StrictQueryParamMixin` rejects requests with unknown query parameters (returns 400). Applied to `MoistureReadingViewSet`, `PumpActionViewSet` and `ScheduleViewSet`.

## Configuration

All via `.env` (see `.env.example` for documentation of each):
- `ARDUINO_ADDRESS` / `ARDUINO_ENABLED` — Arduino IP on the LAN, and whether to actually call it
- `CORS_ALLOWED_ORIGINS` / `ALLOWED_HOSTS` — must include the frontend's origin for deployment
- `LATITUDE` / `LONGITUDE` / `LOCAL_TIMEZONE` — location for ET0 and local-time scheduling (Django's `TIME_ZONE` stays UTC)
- `HEALTHCHECKS_URL`, `HC_*` — monitoring
- Database is SQLite (`db.sqlite3`, gitignored)

## System Overview

Pflaenzli is split across three sibling repos under `../` (`pflaenzli_arduino`, `pflaenzli_backend`, `pflaenzli_frontend`). Each has its own CLAUDE.md; this section is kept identical in all three.

```
browser ──HTTPS──▶ nginx (basic auth) ──/api/──▶ backend (gunicorn :8000) ◀── cron: POST /internal/tick (every minute)
                                                    │                ▲
                     PUT /configuration,            │                │  GET /api/configuration/1 (boot, retried until success)
                     PUT /pump/start|stop,          ▼                │  POST /api/sensor   (each reading)
                     PUT /triggerMeasurement     Arduino (HTTP :80) ─┘  POST /api/pump     (each pump on/off)
```

- **Backend is the hub.** The frontend talks only to the backend (never to the Arduino). The backend pushes commands to the Arduino, and the Arduino reports back to the backend.
- **Scheduling lives in the backend.** The minutely tick plans the day once (Open-Meteo ET0 → number of pump events spread over the watering window) and fires due events by sending `pump/start` to the Arduino. The Arduino knows nothing about schedules: each start runs one cycle (open valve, wait `valve_duration`, pump for `pump_duration`, close both). Automatic moisture measurements run on the Arduino's own timer (`measurement_interval`).
- **`PumpAction` rows reflect the real pump state.** They are only created when the Arduino reports via `POST /api/pump`. Manual starts and scheduled starts only relay the command.
- **Shared contract:** the JSON config fields `measurement_interval`, `pump_duration`, `valve_duration`, `measurement_enabled`, `pump_enabled` are used by all three repos, so renaming one touches all three. The irrigation fields (`pump_seconds_per_mm`, `calc_time`, `window_start`, `window_end`) are used only by the backend and frontend.
- **Monitoring:** each tick reports to healthchecks.io (dead-man's switch: stale moisture readings, scheduled starts the Arduino never confirmed).
- **Production** runs on a Raspberry Pi on the LAN: nginx serves the built frontend and proxies `/api/` to the gunicorn systemd service. `/internal/` is not proxied. Deploys are pull-based: push `main` to GitHub, then `git pull` on the Pi. The repos are public, so IPs, coordinates and secrets stay in gitignored files (`arduino_secrets.h`, backend `.env`, frontend `.env.production`).
