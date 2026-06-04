from django.core.management.base import BaseCommand, CommandError

from fantasy.models import SyncRun
from fantasy.services.sources import import_default_sources


class Command(BaseCommand):
    help = "Import the FIFA World Cup 2026 schedule and store source snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--openfootball-file", help="Read OpenFootball JSON from a local fixture file.")
        parser.add_argument("--skip-remote-fifa", action="store_true", help="Skip FIFA page downloads and only parse OpenFootball.")

    def handle(self, *args, **options):
        run = SyncRun.objects.create(kind=SyncRun.Kind.IMPORT)
        try:
            details = import_default_sources(
                openfootball_file=options.get("openfootball_file"),
                skip_remote_fifa=options.get("skip_remote_fifa"),
            )
        except Exception as exc:
            run.finish(message=f"Import failed: {exc}")
            raise CommandError(str(exc)) from exc
        run.finish(updated_matches=details.get("updated", 0), message="Schedule import completed.", details=details)
        self.stdout.write(self.style.SUCCESS(f"Imported {details.get('updated', 0)} matches."))
