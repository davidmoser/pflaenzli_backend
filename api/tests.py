import datetime
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from . import dispatcher, planner
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
        window_end=datetime.time(20, 0), latitude=47.3769, longitude=8.5417,
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
            fired = dispatcher.tick()

        self.assertEqual(fired, 1)
        mock_start_pump.assert_called_once_with()
        # The PumpAction row is written by the Arduino's POST /api/pump, not the dispatcher.
        self.assertEqual(ScheduledPumpAction.objects.count(), 0)

    @mock.patch.object(dispatcher.actions, 'start_pump')
    def test_future_actions_are_not_fired(self, mock_start_pump):
        ScheduledPumpAction.objects.create(time=datetime.time(15, 0))  # after noon

        with mock.patch.object(planner, 'local_now', return_value=self.now):
            fired = dispatcher.tick()

        self.assertEqual(fired, 0)
        mock_start_pump.assert_not_called()
        self.assertEqual(ScheduledPumpAction.objects.count(), 1)
