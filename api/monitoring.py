"""Dead-man's-switch reporting to healthchecks.io.

Called once per tick. Sends a single ping: the success URL when everything looks healthy,
or ``URL/fail`` with a human-readable reason in the body when something is wrong. The Pi
being alive is itself the proof for the success ping — a crashed/offline Pi simply stops
pinging, and healthchecks trips the check on its own (period + grace).

This must never raise: a monitoring hiccup must not affect watering (see the past
worker-hang incident that motivated ARDUINO_TIMEOUT).
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from . import planner
from .models import MoistureReading, PumpAction

logger = logging.getLogger(__name__)


def _ping(base_url, failed, data):
    """POST to the success URL, or base_url + '/fail' when ``failed``. Never raises."""
    if not base_url:
        return
    url = base_url + "/fail" if failed else base_url
    try:
        requests.post(url, data=data, timeout=5)
    except requests.RequestException:
        logger.warning("healthchecks ping to %s failed", url, exc_info=True)


def report(config, error=None):
    """Send one healthchecks ping reflecting the current health of the system.

    ``error`` is an exception captured by the tick, if any; it is reported first so the
    reason survives even when the failure prevented the checks below from running.
    """
    if not settings.HEALTHCHECKS_URL:
        return

    problems = []
    data = {}
    if error is not None:
        problems.append(f"tick exception: {type(error).__name__}: {error}"[:200])

    try:
        now = timezone.now()
        local = planner.local_now()
        in_window = config.window_start <= local.time() <= config.window_end

        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        pumps_today = PumpAction.objects.filter(
            action=True, timestamp__gte=midnight).count()
        last_pump = PumpAction.objects.filter(action=True).order_by("-timestamp").first()

        # The Arduino posts a moisture reading every measurement_interval; treat a gap as
        # the device being offline. Skip when measurement is disabled (silence is expected).
        last_measurement = MoistureReading.objects.order_by("-timestamp").first()
        if config.measurement_enabled:
            if (last_measurement is None
                    or now - last_measurement.timestamp
                    > timedelta(minutes=settings.HC_ARDUINO_STALE_MINUTES)):
                problems.append("no arduino contact")

        # No watering for too long during the daytime window. Measure staleness from the
        # later of the window start and the last pump, so the morning ramp and overnight
        # gap can't false-alarm.
        if in_window:
            ws = config.window_start
            since = local.replace(hour=ws.hour, minute=ws.minute, second=ws.second,
                                  microsecond=0)
            if last_pump is not None and last_pump.timestamp > since:
                since = last_pump.timestamp
            if now - since > timedelta(minutes=settings.HC_WATERING_STALE_MINUTES):
                problems.append("no watering")

        data = {
            "pumps_today": pumps_today,
            "last_measurement": last_measurement.timestamp.isoformat() if last_measurement else "never",
            "last_pump": last_pump.timestamp.isoformat() if last_pump else "never",
        }
    except Exception:
        logger.exception("monitoring self-check failed")
        problems.append("monitoring self-check failed")

    data["status"] = " | ".join(problems) if problems else "ok"
    _ping(settings.HEALTHCHECKS_URL, bool(problems), data)
