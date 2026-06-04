from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from fantasy.models import DataSnapshot, Match, SyncRun
from fantasy.services.sources import flag_emoji


FIXTURE_DIR = Path(__file__).resolve().parent


class ImportSyncTests(TestCase):
    def test_import_schedule_from_fixture(self):
        call_command(
            "import_schedule",
            openfootball_file=str(FIXTURE_DIR / "fixtures_openfootball.json"),
            skip_remote_fifa=True,
        )
        self.assertEqual(Match.objects.count(), 3)
        match = Match.objects.get(match_number=1)
        self.assertEqual(match.home_team.flag, flag_emoji("MX"))
        self.assertEqual(match.away_team.flag, flag_emoji("ZA"))
        self.assertEqual(Match.objects.get(match_number=73).stage, Match.Stage.ROUND_OF_32)
        self.assertEqual(DataSnapshot.objects.filter(source=DataSnapshot.Source.OPENFOOTBALL, parsed_ok=True).count(), 1)
        self.assertEqual(SyncRun.objects.filter(kind=SyncRun.Kind.IMPORT).count(), 1)

    def test_sync_scores_updates_and_is_idempotent(self):
        call_command(
            "import_schedule",
            openfootball_file=str(FIXTURE_DIR / "fixtures_openfootball.json"),
            skip_remote_fifa=True,
        )
        call_command("sync_scores", openfootball_file=str(FIXTURE_DIR / "fixtures_openfootball_scores.json"))
        call_command("sync_scores", openfootball_file=str(FIXTURE_DIR / "fixtures_openfootball_scores.json"))
        match = Match.objects.get(match_number=1)
        self.assertEqual(match.status, Match.Status.FINAL)
        self.assertEqual((match.home_score, match.away_score), (2, 1))
        self.assertEqual(SyncRun.objects.filter(kind=SyncRun.Kind.SCORE_SYNC).count(), 2)
