"""Tick dispatcher: runs in-process on the already-running server.

Driven by a once-a-minute cron call to the internal tick endpoint. Planning is
folded into the tick so a missed run is self-healing.
"""
import logging

from . import actions, monitoring, planner
from .models import Schedule, ScheduledPumpAction

logger = logging.getLogger(__name__)


def tick():
    """One scheduler tick: maybe plan today, then fire one pump cycle if any action is due."""
    config = planner.get_config()

    error = None
    planned = pump_action = None
    try:
        planned = _maybe_plan(config)
        pump_action = _fire_due_actions(config)
    except Exception as exc:
        error = exc
        logger.exception("tick failed")
    finally:
        monitoring.report(config, error=error)

    if error is not None:
        raise error
    return planned, pump_action


def _maybe_plan(config):
    now = planner.local_now()
    if Schedule.objects.filter(schedule_date=now.date()).exists():
        return False
    if now.time() < config.calc_time:
        return False
    planner.plan_today(config=config)
    return True


def _fire_due_actions(config):
    """Fire at most one pump cycle per tick, clearing every currently-due action.

    The Arduino pump is asynchronous and idempotent: a start command returns immediately
    and the fixed-length pump cycle runs in the firmware loop. Firing several overdue
    actions in a burst would therefore collapse into a single watering, so after an outage
    we trigger one cycle and mark all the overdue actions fired rather than re-firing each.
    In normal operation only one action is ever due per tick.

    The PumpAction record is written by the Arduino reporting its real on/off state to
    POST /api/pump (the same source as a manual pump), so we don't record one here.
    Monitoring checks that the last fired action is followed by such a record.
    """
    now_time = planner.local_now().time()
    due = ScheduledPumpAction.objects.filter(fired_at__isnull=True, time__lte=now_time)
    count = due.count()
    if not count:
        return False

    actions.start_pump()
    due.update(fired_at=now_time)

    logger.info("Fired pump for %ss (marked %d due action(s) fired)", config.pump_duration, count)
    return True
