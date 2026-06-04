from django.core.management.base import BaseCommand, CommandError

from fantasy.models import SyncRun
from fantasy.services.sources import sync_scores_from_openfootball


class Command(BaseCommand):
    help = "Synchronize match scores from configured free sources."

    def add_arguments(self, parser):
        parser.add_argument("--openfootball-file", help="Read OpenFootball JSON from a local fixture file.")

    def handle(self, *args, **options):
        run = SyncRun.objects.create(kind=SyncRun.Kind.SCORE_SYNC)
        try:
            details = sync_scores_from_openfootball(openfootball_file=options.get("openfootball_file"))
        except Exception as exc:
            run.finish(message=f"Score sync failed: {exc}")
            raise CommandError(str(exc)) from exc
        run.finish(
            updated_matches=details["updated"],
            conflict_count=len(details["conflicts"]),
            message="Score sync completed.",
            details=details,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {details['updated']} matches with {len(details['conflicts'])} conflicts."
            )
        )
