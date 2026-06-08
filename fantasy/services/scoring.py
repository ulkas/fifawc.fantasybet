from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch

from fantasy.models import Match, Player, Prediction


@dataclass
class RankingRow:
    player: Player
    points: int
    correct: int
    wrong: int
    no_bet_points: int
    predictions: int


@dataclass
class ScoreRange:
    min_points: int
    max_points: int


def points_for(player: Player, match: Match, prediction: Prediction | None) -> int:
    if not match.is_scored:
        return 0
    if prediction is None or prediction.choice == Prediction.Choice.NONE:
        return 1
    if prediction.choice == match.actual_outcome:
        return 3
    return 0


def score_range() -> ScoreRange:
    scored_count = Match.objects.filter(status=Match.Status.FINAL, home_score__isnull=False, away_score__isnull=False).count()
    # Preliminary max is based on matches already scored
    return ScoreRange(min_points=scored_count, max_points=scored_count * 3)


def ranking_rows() -> list[RankingRow]:
    scored_matches = list(Match.objects.filter(status=Match.Status.FINAL, home_score__isnull=False, away_score__isnull=False))
    players = Player.objects.prefetch_related(
        Prefetch("predictions", queryset=Prediction.objects.select_related("match"))
    )
    rows: list[RankingRow] = []
    for player in players:
        by_match = {prediction.match_id: prediction for prediction in player.predictions.all()}
        points = 0
        correct = 0
        wrong = 0
        no_bet_points = 0
        for match in scored_matches:
            prediction = by_match.get(match.id)
            match_points = points_for(player, match, prediction)
            points += match_points
            if prediction is None or prediction.choice == Prediction.Choice.NONE:
                no_bet_points += match_points
            elif match_points == 3:
                correct += 1
            else:
                wrong += 1
        rows.append(
            RankingRow(
                player=player,
                points=points,
                correct=correct,
                wrong=wrong,
                no_bet_points=no_bet_points,
                predictions=len(by_match),
            )
        )
    return sorted(rows, key=lambda row: (-row.points, -row.correct, row.player.nick))


def player_prediction_rows(player: Player) -> list[dict]:
    predictions = {prediction.match_id: prediction for prediction in Prediction.objects.filter(player=player)}
    rows = []
    for match in Match.objects.select_related("home_team", "away_team", "venue"):
        prediction = predictions.get(match.id)
        rows.append(
            {
                "match": match,
                "prediction": prediction,
                "points": points_for(player, match, prediction),
            }
        )
    return rows
