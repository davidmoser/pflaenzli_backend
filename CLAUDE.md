# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pflaenzli Backend is a Django REST API that serves as the hub between an Arduino plant-watering device and a Vue frontend. It stores moisture readings and pump actions from the Arduino, provides configuration to it, and exposes all data to the frontend.

## Development Commands

```bash
# Activate virtualenv
source venv/bin/activate

# Run dev server (port 8000)
python manage.py runserver 0.0.0.0:8000

# Run all tests
python manage.py test

# Run a single test class or method
python manage.py test api.tests.StrictQueryParamMixinTests
python manage.py test api.tests.StrictQueryParamMixinTests.test_sensor_unknown_query_param_returns_400

# Apply migrations
python manage.py migrate

# Load initial configuration fixture
python manage.py loaddata configuration
```

No linting or type-checking tools are configured.

## Architecture

Single Django app (`api`) with Django REST Framework. All URLs are registered via a `DefaultRouter` at `/api/` with `trailing_slash=False`.

### Models

- **MoistureReading** — timestamped soil moisture value (integer)
- **PumpAction** — timestamped pump on/off event (boolean)
- **Configuration** — singleton (pk=1) with runtime parameters: `measurement_interval`, `pump_duration`, `valve_duration`, `measurement_enabled`, `pump_enabled`

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

### Arduino Communication (`api/actions.py`)

The backend forwards commands to the Arduino via HTTP requests to `settings.ARDUINO_ADDRESS`. When `DEBUG=True`, Arduino communication is disabled (`ARDUINO_ENABLED = not DEBUG`), so the dev server works without hardware.

### Query Parameter Validation

`StrictQueryParamMixin` rejects requests with unknown query parameters (returns 400). Applied to `MoistureReadingViewSet` and `PumpActionViewSet`.

## Configuration

- `ARDUINO_ADDRESS` in `settings.py` — IP of the Arduino on the local network
- `CORS_ALLOWED_ORIGINS` / `ALLOWED_HOSTS` — must include the frontend's origin for deployment
- Database is SQLite (`db.sqlite3`, gitignored)

## Related Projects

- **pflaenzli_arduino** — Arduino firmware (sibling directory)
- **pflaenzli_frontend** — Vue 3 frontend (sibling directory)
