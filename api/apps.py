from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'


@receiver(connection_created)
def set_sqlite_pragmas(sender, connection, **kwargs):
    """Enable WAL mode so the single writer (gunicorn) and readers don't block.

    busy_timeout makes brief lock contention wait rather than error out.
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA busy_timeout=5000;')
