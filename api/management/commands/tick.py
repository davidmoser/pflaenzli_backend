"""Manual debugging wrapper around the dispatcher tick.

Cron drives the internal HTTP endpoint, not this command; this is only for manual
runs while debugging.
"""
from django.core.management.base import BaseCommand

from api import dispatcher


class Command(BaseCommand):
    help = "Run one scheduler tick (plan if due, fire due actions)."

    def handle(self, *args, **options):
        planned, pump_action = dispatcher.tick()
        self.stdout.write(self.style.SUCCESS(f"Tick complete. planned {planned}, pump action {pump_action}"))
