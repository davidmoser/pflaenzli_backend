from rest_framework import serializers

from .models import MoistureReading, PumpAction, Configuration, ScheduledPumpAction, Schedule


class MoistureReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoistureReading
        fields = ['id', 'timestamp', 'moisture_level']


class PumpActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PumpAction
        fields = ['id', 'timestamp', 'action']


class ScheduledPumpActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledPumpAction
        fields = ['id', 'time']


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'


class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = [
            'id',
            'measurement_interval', 'pump_duration', 'valve_duration',
            'measurement_enabled', 'pump_enabled',
            'pump_seconds_per_mm',
            'calc_time', 'window_start', 'window_end',
            'latitude', 'longitude',
        ]
