from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from fantasy.models import Match, Player, Prediction, Venue
from fantasy.services.scoring import player_prediction_rows, ranking_rows, score_range


class ScoringTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Mexico City")
        self.match = Match.objects.create(
            match_number=1,
            group="Group A",
            kickoff_at=timezone.now() - timedelta(hours=2),
            venue=self.venue,
            home_label="Mexico",
            away_label="South Africa",
            status=Match.Status.FINAL,
            home_score=2,
            away_score=1,
        )
        self.player = Player.objects.create(nick="ana", display_name="Ana", pin_hash="x")

    def test_correct_win_scores_three(self):
        prediction = Prediction.objects.create(player=self.player, match=self.match, choice=Prediction.Choice.HOME)
        self.assertEqual(prediction.points(), 3)
        self.assertEqual(ranking_rows()[0].points, 3)

    def test_wrong_bet_scores_zero(self):
        prediction = Prediction.objects.create(player=self.player, match=self.match, choice=Prediction.Choice.AWAY)
        self.assertEqual(prediction.points(), 0)
        self.assertEqual(ranking_rows()[0].points, 0)

    def test_no_bet_and_missing_score_one_after_final(self):
        self.assertEqual(player_prediction_rows(self.player)[0]["points"], 1)
        Prediction.objects.create(player=self.player, match=self.match, choice=Prediction.Choice.NONE)
        self.assertEqual(ranking_rows()[0].points, 1)

    def test_upcoming_match_not_locked_before_kickoff(self):
        upcoming = Match.objects.create(
            match_number=2,
            kickoff_at=timezone.now() + timedelta(minutes=10),
            venue=self.venue,
            home_label="Brazil",
            away_label="Morocco",
        )
        self.assertFalse(upcoming.is_locked)

    def test_score_range_is_static_for_the_league(self):
        Prediction.objects.create(player=self.player, match=self.match, choice=Prediction.Choice.HOME)
        Match.objects.create(
            match_number=2,
            kickoff_at=timezone.now() + timedelta(minutes=10),
            venue=self.venue,
            home_label="Brazil",
            away_label="Morocco",
        )
        Match.objects.create(
            match_number=3,
            kickoff_at=timezone.now() + timedelta(minutes=20),
            venue=self.venue,
            home_label="Canada",
            away_label="USA",
        )

        league_range = score_range()

        self.assertEqual(league_range.min_points, 1)
        self.assertEqual(league_range.max_points, 9)
