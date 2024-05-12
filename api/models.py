from django.db import models


class MoistureReading(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    moisture_level = models.IntegerField()

    def __str__(self):
        return f"{self.timestamp} - Moisture Level: {self.moisture_level}"


class PumpAction(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.timestamp} - Pump Action: {self.action}"


class Configuration(models.Model):
    measurement_enabled = models.BooleanField(default=True)
    measurement_interval = models.IntegerField(help_text="Interval in seconds")
    pump_enabled = models.BooleanField(default=True)
    pump_duration = models.IntegerField(help_text="Duration in seconds")
    max_consecutive_pumps = models.IntegerField(default=0)
    moisture_threshold = models.IntegerField(default=0)

    def __str__(self):
        return "System Configuration"
