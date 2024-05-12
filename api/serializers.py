from rest_framework import serializers

from .models import MoistureReading, PumpAction, Configuration


class MoistureReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoistureReading
        fields = ['id', 'timestamp', 'moisture_level']


class PumpActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PumpAction
        fields = ['id', 'timestamp', 'action']


class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = [
            'id',
            'moisture_threshold', 'measurement_interval', 'pump_duration',
            'max_consecutive_pumps', 'measurement_enabled', 'pump_enabled'
        ]
