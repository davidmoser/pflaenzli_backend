from django.test import TestCase
from rest_framework.test import APIClient

from .models import MoistureReading, PumpAction


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
