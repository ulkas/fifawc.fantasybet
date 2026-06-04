from django.core.management.base import BaseCommand

from fantasy.services.scoring import ranking_rows


class Command(BaseCommand):
    help = "Print the current fantasy ranking without mutating stored data."

    def handle(self, *args, **options):
        for index, row in enumerate(ranking_rows(), start=1):
            self.stdout.write(f"{index}. {row.player.display_name}: {row.points}")
