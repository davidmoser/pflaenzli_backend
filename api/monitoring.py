"""Dead-man's-switch reporting to healthchecks.io.

Called once per tick. Sends a single ping: the success URL when everything looks healthy,
or ``URL/fail`` with a human-readable reason in the body when something is wrong. The Pi
being alive is itself the proof for the success ping — a crashed/offline Pi simply stops
pinging, and healthchecks trips the check on its own (period + grace).

This must never raise: a monitoring hiccup must not affect watering (see the past
worker-hang incident that motivated ARDUINO_TIMEOUT).
"""
import logging
from datetime import datetime, timedelta

import requests
from django.conf import settings

from . import planner
from .models import MoistureReading, PumpAction, ScheduledPumpAction

logger = logging.getLogger(__name__)


def _fmt(ts):
    """Format a UTC timestamp as local time to the minute, or 'never'."""
    if ts is None:
        return "never"
    return ts.astimezone(planner.LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


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

    # The tick runs every minute; only actually ping every HC_PING_INTERVAL_MINUTES so the
    # healthchecks event log stays readable. Stateless: keyed off the wall clock.
    local = planner.local_now()
    interval = settings.HC_PING_INTERVAL_MINUTES
    if interval > 0 and local.minute % interval != 0:
        return

    problems = []
    data = {}
    if error is not None:
        problems.append(f"tick exception: {type(error).__name__}: {error}"[:200])

    try:
        now = local

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

        # The last fired scheduled pump action should be followed by the Arduino reporting
        # the pump on within the grace period. Pump actions are far more than a ping interval
        # apart, so checking only the last one covers them all. fired_at is a local time;
        # yesterday's rows (present until the morning plan) land in the future and are skipped.
        grace = timedelta(minutes=settings.HC_PUMP_CONFIRM_MINUTES)
        last_fired = (ScheduledPumpAction.objects.filter(fired_at__isnull=False)
                      .order_by("-fired_at").first())
        if last_fired is not None:
            fired_at = datetime.combine(local.date(), last_fired.fired_at,
                                        tzinfo=planner.LOCAL_TZ)
            if (fired_at <= now - grace
                    and not PumpAction.objects.filter(
                        action=True, timestamp__gte=fired_at,
                        timestamp__lte=fired_at + grace).exists()):
                problems.append(f"pump fired at {last_fired.fired_at:%H:%M} not confirmed")

        data = {
            "pumps_today": pumps_today,
            "last_measurement": _fmt(last_measurement.timestamp if last_measurement else None),
            "last_pump": _fmt(last_pump.timestamp if last_pump else None),
        }
    except Exception:
        logger.exception("monitoring self-check failed")
        problems.append("monitoring self-check failed")

    if problems:
        # On failure, send only the reason — the pumps/measurement info is visible in the
        # preceding success pings anyway, and keeping the fail body terse makes it scannable.
        _ping(settings.HEALTHCHECKS_URL, True, {"status": " | ".join(problems)})
    else:
        data["status"] = "ok"
        _ping(settings.HEALTHCHECKS_URL, False, data)
