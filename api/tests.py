import datetime
from unittest import mock

import requests
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from . import dispatcher, monitoring, planner
from .models import (
    Configuration, MoistureReading, PumpAction, Schedule, ScheduledPumpAction,
)


def make_schedule(date, **overrides):
    fields = dict(schedule_date=date, et0=3.0)
    fields.update(overrides)
    return Schedule.objects.create(**fields)


def make_config(**overrides):
    fields = dict(
        measurement_interval=600, pump_duration=60, valve_duration=7,
        measurement_enabled=True, pump_enabled=True,
        pump_seconds_per_mm=10.0,
        calc_time=datetime.time(6, 0), window_start=datetime.time(7, 0),
        window_end=datetime.time(20, 0),
    )
    fields.update(overrides)
    return Configuration.objects.create(**fields)


class StrictQueryParamMixinTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_sensor_unknown_query_param_returns_400(self):
        MoistureReading.objects.create(moisture_level=42)

        response = self.client.get('/api/sensor?start=2026-02-17T15:02:55%2B01:00&end=2026-03-17T15:02:55%2B01:00&foo=bar')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'detail': 'Unknown query parameter(s): foo'})

    def test_sensor_valid_query_params_return_200(self):
        MoistureReading.objects.create(moisture_level=42)

        response = self.client.get('/api/sensor?start=2026-02-17T15:02:55%2B01:00&end=2026-03-17T15:02:55%2B01:00')

        self.assertEqual(response.status_code, 200)

    def test_pump_unknown_query_param_returns_400(self):
        PumpAction.objects.create(action=True)

        response = self.client.get('/api/pump?start=2026-02-17T15:02:55%2B01:00&end=2026-03-17T15:02:55%2B01:00&invalid=true')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'detail': 'Unknown query parameter(s): invalid'})


class EventCalcTests(TestCase):
    def test_events_for_et0(self):
        # 10 s/mm, 10 mm -> 100 pump-s; event=60 s -> ceil(100/60) = 2.
        self.assertEqual(planner.events_for_et0(10.0, 60, 10.0), 2)

    def test_events_for_et0_exact_multiple(self):
        # 10 s/mm, 12 mm -> 120 pump-s; event=60 s -> 120/60 = 2.
        self.assertEqual(planner.events_for_et0(10.0, 60, 12.0), 2)

    def test_events_for_et0_zero(self):
        self.assertEqual(planner.events_for_et0(10.0, 60, 0.0), 0)

    def test_events_for_et0_guards_nonpositive(self):
        self.assertEqual(planner.events_for_et0(0.0, 60, 10.0), 0)
        self.assertEqual(planner.events_for_et0(10.0, 0, 10.0), 0)


class PlannerTests(TestCase):
    def setUp(self):
        self.config = make_config()

    @mock.patch.object(planner, 'fetch_et0', return_value=10.0)
    def test_plan_today_writes_actions_and_schedule(self, _mock):
        n = planner.plan_today(config=self.config)
        self.assertEqual(n, 2)
        self.assertEqual(ScheduledPumpAction.objects.count(), 2)

        today = planner.local_today()
        schedule = Schedule.objects.get(schedule_date=today)
        self.assertEqual(schedule.et0, 10.0)

    @mock.patch.object(planner, 'fetch_et0', return_value=10.0)
    def test_replan_discards_prior_actions_and_schedule(self, _mock):
        ScheduledPumpAction.objects.create(time=datetime.time(9, 0))
        ScheduledPumpAction.objects.create(time=datetime.time(10, 0))
        make_schedule(planner.local_today(), et0=99.0)
        with self.assertLogs('api.planner', level='WARNING') as logs:
            planner.plan_today(config=self.config)
        self.assertTrue(any('discarding' in m for m in logs.output))
        # Only the freshly planned actions and a single fresh Schedule remain.
        self.assertEqual(ScheduledPumpAction.objects.count(), 2)
        self.assertEqual(Schedule.objects.count(), 1)
        self.assertEqual(Schedule.objects.get().et0, 10.0)


def _ok_response(et0):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"daily": {"et0_fao_evapotranspiration": [et0]}}
    return resp


def _error_response(status=503):
    resp = mock.Mock()
    resp.status_code = status
    resp.text = "Service Unavailable"
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class FetchEt0Tests(TestCase):
    @mock.patch.object(planner.time, 'sleep')
    @mock.patch.object(planner.requests, 'get')
    def test_retries_transient_error_then_succeeds(self, mock_get, mock_sleep):
        # The recurring morning symptom: first request 503s, the retry returns the value.
        mock_get.side_effect = [_error_response(503), _ok_response(4.2)]

        with self.assertLogs('api.planner', level='WARNING'):
            self.assertEqual(planner.fetch_et0(), 4.2)

        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(planner.ET0_FETCH_RETRY_DELAY)

    @mock.patch.object(planner.time, 'sleep')
    @mock.patch.object(planner.requests, 'get')
    def test_raises_after_exhausting_attempts(self, mock_get, _mock_sleep):
        mock_get.side_effect = [_error_response(503)] * planner.ET0_FETCH_ATTEMPTS

        with self.assertRaises(requests.HTTPError):
            with self.assertLogs('api.planner', level='WARNING'):
                planner.fetch_et0()

        self.assertEqual(mock_get.call_count, planner.ET0_FETCH_ATTEMPTS)


class TickEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.config = make_config()
        # Today already planned, so the tick does not fetch ET0 / contact hardware.
        make_schedule(planner.local_today())

    def test_non_localhost_rejected(self):
        response = self.client.post('/internal/tick', REMOTE_ADDR='10.0.0.5')
        self.assertEqual(response.status_code, 403)

    def test_localhost_accepted(self):
        response = self.client.post('/internal/tick', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')


class DispatcherTests(TestCase):
    def setUp(self):
        self.config = make_config()
        # Pin "now" to noon today so the due/not-due comparison is deterministic.
        today = planner.local_today()
        self.now = datetime.datetime.combine(
            today, datetime.time(12, 0), tzinfo=planner.LOCAL_TZ)
        # Today already planned, so the tick does not fetch ET0.
        make_schedule(today)

    @mock.patch.object(dispatcher.actions, 'start_pump')
    def test_overdue_actions_collapse_into_one_pump_cycle(self, mock_start_pump):
        for hour in (9, 10, 11):  # all before the pinned noon
            ScheduledPumpAction.objects.create(time=datetime.time(hour, 0))

        with mock.patch.object(planner, 'local_now', return_value=self.now):
            planned, pump_action = dispatcher.tick()

        self.assertFalse(planned)  # today already planned in setUp
        self.assertTrue(pump_action)
        mock_start_pump.assert_called_once_with()
        # The PumpAction row is written by the Arduino's POST /api/pump, not the dispatcher.
        # All due actions are stamped with one shared fired_at.
        fired_at = set(ScheduledPumpAction.objects.values_list('fired_at', flat=True))
        self.assertEqual(len(fired_at), 1)
        self.assertIsNotNone(fired_at.pop())

    @mock.patch.object(dispatcher.actions, 'start_pump')
    def test_already_fired_actions_are_not_refired(self, mock_start_pump):
        ScheduledPumpAction.objects.create(
            time=datetime.time(9, 0), fired_at=datetime.time(9, 0))

        with mock.patch.object(planner, 'local_now', return_value=self.now):
            planned, pump_action = dispatcher.tick()

        self.assertFalse(pump_action)
        mock_start_pump.assert_not_called()

    @mock.patch.object(dispatcher.actions, 'start_pump')
    def test_future_actions_are_not_fired(self, mock_start_pump):
        ScheduledPumpAction.objects.create(time=datetime.time(15, 0))  # after noon

        with mock.patch.object(planner, 'local_now', return_value=self.now):
            planned, pump_action = dispatcher.tick()

        self.assertFalse(planned)  # today already planned in setUp
        self.assertFalse(pump_action)
        mock_start_pump.assert_not_called()
        self.assertIsNone(ScheduledPumpAction.objects.get().fired_at)


@override_settings(HEALTHCHECKS_URL='https://hc.example/ping', HC_PING_INTERVAL_MINUTES=0,
                   HC_PUMP_CONFIRM_MINUTES=15)
@mock.patch.object(monitoring, '_ping')
class PumpConfirmationMonitoringTests(TestCase):
    def setUp(self):
        self.config = make_config(measurement_enabled=False)
        # Pin "now" to noon today so the fired times don't wrap around midnight.
        self.now = datetime.datetime.combine(
            planner.local_today(), datetime.time(12, 0), tzinfo=planner.LOCAL_TZ)
        patcher = mock.patch.object(planner, 'local_now', return_value=self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fire(self, minutes_ago):
        fired_at = self.now - datetime.timedelta(minutes=minutes_ago)
        ScheduledPumpAction.objects.create(
            time=datetime.time(9, 0), fired_at=fired_at.time())
        return fired_at

    def report_pump_on(self, at):
        pump = PumpAction.objects.create(action=True)
        PumpAction.objects.filter(pk=pump.pk).update(timestamp=at)  # bypass auto_now_add

    def assert_status(self, mock_ping, failed, status):
        _url, sent_failed, data = mock_ping.call_args.args
        self.assertEqual(sent_failed, failed)
        self.assertEqual(data['status'], status)

    def test_confirmed_action_is_ok(self, mock_ping):
        fired_at = self.fire(minutes_ago=30)
        self.report_pump_on(fired_at + datetime.timedelta(seconds=10))
        monitoring.report(self.config)
        self.assert_status(mock_ping, False, 'ok')

    def test_unconfirmed_action_fails(self, mock_ping):
        fired_at = self.fire(minutes_ago=30)
        monitoring.report(self.config)
        self.assert_status(
            mock_ping, True, f"pump fired at {fired_at:%H:%M} not confirmed")

    def test_unconfirmed_action_within_grace_is_ok(self, mock_ping):
        self.fire(minutes_ago=5)
        monitoring.report(self.config)
        self.assert_status(mock_ping, False, 'ok')

    def test_pump_before_firing_does_not_confirm(self, mock_ping):
        fired_at = self.fire(minutes_ago=30)
        self.report_pump_on(fired_at - datetime.timedelta(minutes=1))
        monitoring.report(self.config)
        self.assert_status(
            mock_ping, True, f"pump fired at {fired_at:%H:%M} not confirmed")

    def test_only_last_fired_action_is_checked(self, mock_ping):
        self.fire(minutes_ago=90)  # unconfirmed, but no longer the last one
        fired_at = self.fire(minutes_ago=30)
        self.report_pump_on(fired_at + datetime.timedelta(seconds=10))
        monitoring.report(self.config)
        self.assert_status(mock_ping, False, 'ok')

    def test_yesterdays_late_fired_action_is_ignored(self, mock_ping):
        self.fire(minutes_ago=-60)  # 13:00, i.e. fired yesterday, before today's plan
        monitoring.report(self.config)
        self.assert_status(mock_ping, False, 'ok')

    def test_unfired_and_no_actions_are_ok(self, mock_ping):
        ScheduledPumpAction.objects.create(time=datetime.time(9, 0))
        monitoring.report(self.config)
        self.assert_status(mock_ping, False, 'ok')
