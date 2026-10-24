from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from news.collect import collect


class Command(BaseCommand):
    help = "Bekannte lokale Quellen abrufen und versionieren"

    def handle(self, *args, **options):
        locked = False
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(735291)")
                locked = cursor.fetchone()[0]
            if not locked:
                self.stdout.write("Ein Sammler läuft bereits.")
                return
        try:
            failures = collect()
            if failures:
                raise CommandError(f"{failures} Quellen konnten nicht aktualisiert werden")
        finally:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(735291)")
