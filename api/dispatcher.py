"""Tick dispatcher: runs in-process on the already-running server.

Driven by a once-a-minute cron call to the internal tick endpoint. Planning is
folded into the tick so a missed run is self-healing.
"""
import logging

from . import actions, planner
from .models import Schedule, ScheduledPumpAction

logger = logging.getLogger(__name__)


def tick():
    """One scheduler tick: maybe plan today, then fire one pump cycle if any action is due."""
    config = planner.get_config()

    _maybe_plan(config)
    fired = _fire_due_actions(config)
    return fired


def _maybe_plan(config):
    now = planner.local_now()
    if Schedule.objects.filter(schedule_date=now.date()).exists():
        return
    if now.time() < config.calc_time:
        return
    planner.plan_today(config=config)


def _fire_due_actions(config):
    """Fire at most one pump cycle per tick, clearing every currently-due action.

    The Arduino pump is asynchronous and idempotent: a start command returns immediately
    and the fixed-length pump cycle runs in the firmware loop. Firing several overdue
    actions in a burst would therefore collapse into a single watering, so after an outage
    we trigger one cycle and discard all the overdue actions rather than re-firing each.
    In normal operation only one action is ever due per tick.

    The PumpAction record is written by the Arduino reporting its real on/off state to
    POST /api/pump (the same source as a manual pump), so we don't record one here.
    """
    now_time = planner.local_now().time()
    due = ScheduledPumpAction.objects.filter(time__lte=now_time)
    count = due.count()
    if not count:
        return 0

    actions.start_pump()
    due.delete()

    logger.info("Fired pump for %ss (cleared %d due action(s))", config.pump_duration, count)
    return 1
