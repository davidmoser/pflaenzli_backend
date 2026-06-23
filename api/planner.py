"""Daily planner: fetch ET0, compute the day's water demand, and write scheduled actions.

All time-of-day reasoning happens in the project's local timezone (Europe/Zurich),
independent of Django's UTC storage.
"""
import datetime
import logging
import math
from zoneinfo import ZoneInfo

import requests

from .models import Configuration, Schedule, ScheduledPumpAction

logger = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("Europe/Zurich")
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_config():
    return Configuration.objects.get(pk=1)


def local_now():
    return datetime.datetime.now(LOCAL_TZ)


def local_today():
    return local_now().date()


def events_for_et0(pump_seconds_per_mm, event_seconds, et0_mm):
    """Number of fixed-length pump events to satisfy today's ET0.

    The watering time needed is `et0_mm * pump_seconds_per_mm` seconds; each event runs the
    pump for `event_seconds`.
    """
    if pump_seconds_per_mm <= 0 or event_seconds <= 0:
        return 0
    return math.ceil(et0_mm * pump_seconds_per_mm / event_seconds)


def fetch_et0(config, for_date=None):
    """Fetch today's reference evapotranspiration (mm) from Open-Meteo.

    The pots are on a covered balcony, so precipitation is deliberately ignored.
    """
    params = {
        "latitude": config.latitude,
        "longitude": config.longitude,
        "daily": "et0_fao_evapotranspiration",
        "timezone": "Europe/Zurich",
        "forecast_days": 1,
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()["daily"]["et0_fao_evapotranspiration"][0]


def _spread_times(n_actions, window_start, window_end):
    """Return n_actions times spread evenly (centered) across [window_start, window_end]."""
    if n_actions <= 0:
        return []
    start = window_start.hour * 3600 + window_start.minute * 60 + window_start.second
    end = window_end.hour * 3600 + window_end.minute * 60 + window_end.second
    span = max(end - start, 0)
    times = []
    for i in range(n_actions):
        offset = span * (i + 0.5) / n_actions
        secs = int(start + offset)
        times.append(datetime.time(hour=secs // 3600, minute=(secs % 3600) // 60,
                                   second=secs % 60))
    return times


def plan_today(config=None):
    """Compute and write today's scheduled pump actions and Schedule record.

    Idempotent for the day: discards any pre-existing scheduled actions and any prior
    Schedule for today (a warning is logged if either existed), fetches ET0, computes the
    number of constant-rate pump events needed, writes them spread across the watering
    window, and records a Schedule snapshot.
    """
    config = config or get_config()
    today = local_today()

    stale = ScheduledPumpAction.objects.count()
    if stale:
        logger.warning("plan_today: discarding %d pre-existing scheduled action(s)", stale)
    ScheduledPumpAction.objects.all().delete()

    if Schedule.objects.filter(schedule_date=today).exists():
        logger.warning("plan_today: discarding existing Schedule for %s", today)
        Schedule.objects.filter(schedule_date=today).delete()

    et0_mm = fetch_et0(config)

    n_actions = events_for_et0(config.pump_seconds_per_mm, config.pump_duration, et0_mm)

    times = _spread_times(n_actions, config.window_start, config.window_end)
    ScheduledPumpAction.objects.bulk_create(
        [ScheduledPumpAction(time=tm) for tm in times])

    Schedule.objects.create(schedule_date=today, et0=et0_mm)

    logger.info("plan_today: et0=%.2fmm -> %d actions", et0_mm, n_actions)
    return n_actions
