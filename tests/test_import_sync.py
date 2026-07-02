import json
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
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
        self.assertEqual(Match.objects.get(match_number=3).stage, Match.Stage.GROUP)
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

    def test_worldcup26_group_sync_uses_group_and_teams_not_feed_id(self):
        call_command(
            "import_schedule",
            openfootball_file=str(FIXTURE_DIR / "fixtures_openfootball.json"),
            skip_remote_fifa=True,
        )
        payload = {
            "games": [
                {
                    "id": "2",
                    "group": "A",
                    "type": "group",
                    "local_date": "06/11/2026 13:00",
                    "finished": "TRUE",
                    "time_elapsed": "finished",
                    "home_team_name_en": "Mexico",
                    "away_team_name_en": "South Africa",
                    "home_score": "4",
                    "away_score": "2",
                }
            ]
        }
        with NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            fixture_path = handle.name

        call_command("sync_scores", openfootball_file=fixture_path)

        matched = Match.objects.get(match_number=1)
        wrong_id = Match.objects.get(match_number=2)
        self.assertEqual(matched.status, Match.Status.FINAL)
        self.assertEqual((matched.home_score, matched.away_score), (4, 2))
        self.assertEqual((wrong_id.home_score, wrong_id.away_score), (None, None))
    def test_worldcup26_knockout_sync_resolves_third_place_placeholder_variants(self):
        Match.objects.create(
            match_number=74,
            stage=Match.Stage.ROUND_OF_32,
            group="R32",
            round_label="Round of 32",
            kickoff_at=datetime(2026, 6, 29, 16, 30, tzinfo=dt_timezone.utc),
            home_label="1E",
            away_label="3A/B/C/D/F",
            source_payload={
                "home_team_label": "Winner Group E",
                "away_team_label": "3A/B/C/D/F",
            },
        )
        payload = {
            "games": [
                {
                    "id": "74",
                    "group": "R32",
                    "matchday": "4",
                    "local_date": "06/29/2026 16:30",
                    "finished": "FALSE",
                    "time_elapsed": "notstarted",
                    "type": "r32",
                    "home_team_label": "Winner Group E",
                    "away_team_label": "3rd Group A/B/C/D/F",
                    "home_team_name_en": "Germany",
                    "away_team_name_en": "Paraguay",
                    "home_score": "0",
                    "away_score": "0",
                }
            ]
        }
        with NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            fixture_path = handle.name

        call_command("sync_scores", openfootball_file=fixture_path)

        match = Match.objects.get(match_number=74)
        self.assertEqual(match.home_label, "Germany")
        self.assertEqual(match.away_label, "Paraguay")
        self.assertEqual(match.home_team.name, "Germany")
        self.assertEqual(match.away_team.name, "Paraguay")
        self.assertEqual((match.home_score, match.away_score), (0, 0))
    def test_worldcup26_knockout_sync_resolves_match_winner_placeholders(self):
        Match.objects.create(
            match_number=94,
            stage=Match.Stage.ROUND_OF_16,
            group="R16",
            round_label="Round of 16",
            kickoff_at=datetime(2026, 7, 6, 17, 0, tzinfo=dt_timezone.utc),
            home_label="W81",
            away_label="W82",
            source_payload={
                "home_team_label": "W81",
                "away_team_label": "W82",
            },
        )
        payload = {
            "games": [
                {
                    "id": "94",
                    "group": "R16",
                    "matchday": "5",
                    "local_date": "07/06/2026 17:00",
                    "finished": "FALSE",
                    "time_elapsed": "notstarted",
                    "type": "r16",
                    "home_team_label": "Winner Match 81",
                    "away_team_label": "Winner Match 82",
                    "home_team_name_en": "United States",
                    "away_team_name_en": "Belgium",
                    "home_score": "0",
                    "away_score": "0",
                }
            ]
        }
        with NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            fixture_path = handle.name

        call_command("sync_scores", openfootball_file=fixture_path)

        match = Match.objects.get(match_number=94)
        self.assertEqual(match.home_label, "USA")
        self.assertEqual(match.away_label, "Belgium")
        self.assertEqual(match.home_team.name, "USA")
        self.assertEqual(match.away_team.name, "Belgium")
        self.assertEqual((match.home_score, match.away_score), (0, 0))



