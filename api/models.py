from django.db import models


class MoistureReading(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    moisture_level = models.IntegerField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp} - Moisture Level: {self.moisture_level}"


class PumpAction(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp} - Pump Action: {self.action}"


class ScheduledPumpAction(models.Model):
    """One planned, not-yet-executed pump action for the current day (time only)."""
    time = models.TimeField()

    class Meta:
        ordering = ['time']

    def __str__(self):
        return f"Scheduled pump action at {self.time}"


class Schedule(models.Model):
    """A day's planning record, created once each day when scheduling runs.

    Snapshots the ET0 input used for that day's calculation.
    """
    schedule_date = models.DateField()
    et0 = models.FloatField(help_text="Reference evapotranspiration used (mm)")

    class Meta:
        ordering = ['schedule_date']

    def __str__(self):
        return f"Schedule for {self.schedule_date}"


class Configuration(models.Model):
    measurement_enabled = models.BooleanField(default=True)
    measurement_interval = models.IntegerField(help_text="Interval in seconds")
    pump_enabled = models.BooleanField(default=True)
    pump_duration = models.IntegerField(
        help_text="Active pump runtime in seconds (also the per-action duration when scheduling)")
    valve_duration = models.IntegerField(help_text="Duration in seconds")

    # --- Irrigation planning ---
    pump_seconds_per_mm = models.FloatField(
        default=10.0, help_text="Pump runtime in seconds needed per mm of ET0")
    calc_time = models.TimeField(
        default="06:00", help_text="Time of day the daily plan is computed")
    window_start = models.TimeField(
        default="07:00", help_text="Start of the watering window")
    window_end = models.TimeField(
        default="20:00", help_text="End of the watering window")
    latitude = models.FloatField(default=47.3769, help_text="Latitude for the ET0 fetch")
    longitude = models.FloatField(default=8.5417, help_text="Longitude for the ET0 fetch")

    def __str__(self):
        return "System Configuration"
