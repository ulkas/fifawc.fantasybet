from __future__ import annotations
import re

from django.db import models
from django.utils import timezone


class Player(models.Model):
    nick = models.SlugField(max_length=40, unique=True)
    display_name = models.CharField(max_length=60)
    pin_hash = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nick"]

    def __str__(self) -> str:
        return self.display_name


class DeviceSession(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="devices")
    token_hash = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    user_agent = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.player.nick} device"


class PortalSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    iso_code = models.CharField(max_length=3, blank=True)
    flag = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Venue(models.Model):
    name = models.CharField(max_length=140, unique=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    timezone_name = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Match(models.Model):
    class Stage(models.TextChoices):
        GROUP = "group", "Group"
        ROUND_OF_32 = "round_of_32", "Round of 32"
        ROUND_OF_16 = "round_of_16", "Round of 16"
        QUARTER_FINAL = "quarter_final", "Quarter-final"
        SEMI_FINAL = "semi_final", "Semi-final"
        THIRD_PLACE = "third_place", "Third place"
        FINAL = "final", "Final"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        FINAL = "final", "Final"
        POSTPONED = "postponed", "Postponed"

    class Outcome(models.TextChoices):
        HOME = "home", "Home"
        DRAW = "draw", "Draw"
        AWAY = "away", "Away"

    match_number = models.PositiveIntegerField(unique=True)
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.GROUP)
    group = models.CharField(max_length=16, blank=True)
    round_label = models.CharField(max_length=80, blank=True)
    kickoff_at = models.DateTimeField()
    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.SET_NULL)
    home_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="home_matches")
    away_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="away_matches")
    home_label = models.CharField(max_length=140)
    away_label = models.CharField(max_length=140)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kickoff_at", "match_number"]

    def __str__(self) -> str:
        return f"Match {self.match_number}: {self.home_label} v {self.away_label}"

    @property
    def is_locked(self) -> bool:
        return self.status in {self.Status.LIVE, self.Status.FINAL} or timezone.now() >= self.kickoff_at

    @property
    def is_scored(self) -> bool:
        return self.status == self.Status.FINAL and self.home_score is not None and self.away_score is not None

    @property
    def is_knockout(self) -> bool:
        return self.stage != self.Stage.GROUP

    def _scorer_entries(self, side: str) -> list[str]:
        raw_value = (self.source_payload or {}).get(f"{side}_scorers")
        if not raw_value or str(raw_value).strip().lower() == "null":
            return []
        text = str(raw_value).strip()
        if text.startswith("{") and text.endswith("}"):
            text = text[1:-1]
        return [item.strip().strip('"') for item in text.split(",") if item.strip()]

    def _goal_counts_by_period(self, side: str) -> tuple[int, int]:
        regular_time_goals = 0
        extra_time_goals = 0
        for entry in self._scorer_entries(side):
            minute_match = re.search(r"(\d+)(?:\+\d+)?(?:\([A-Z]+\))?'", entry)
            if not minute_match:
                continue
            minute = int(minute_match.group(1))
            if minute > 90:
                extra_time_goals += 1
            else:
                regular_time_goals += 1
        return regular_time_goals, extra_time_goals

    @property
    def regular_time_outcome(self) -> str:
        if not self.is_scored:
            return ""
        if not self.is_knockout:
            if self.home_score > self.away_score:
                return self.Outcome.HOME
            if self.away_score > self.home_score:
                return self.Outcome.AWAY
            return self.Outcome.DRAW

        payload = self.source_payload or {}
        if self.home_score == self.away_score:
            return self.Outcome.DRAW
        if any(str(payload.get(field)).strip().lower() not in ("", "null", "none") for field in ("home_penalty_score", "away_penalty_score")):
            return self.Outcome.DRAW

        home_regular, home_extra = self._goal_counts_by_period("home")
        away_regular, away_extra = self._goal_counts_by_period("away")
        if home_extra or away_extra:
            if home_regular > away_regular:
                return self.Outcome.HOME
            if away_regular > home_regular:
                return self.Outcome.AWAY
            return self.Outcome.DRAW

        if self.home_score > self.away_score:
            return self.Outcome.HOME
        if self.away_score > self.home_score:
            return self.Outcome.AWAY
        return self.Outcome.DRAW

    @property
    def actual_outcome(self) -> str:
        return self.regular_time_outcome

    @property
    def score_label(self) -> str:
        if self.home_score is None or self.away_score is None:
            return "-"
        return f"{self.home_score}-{self.away_score}"


class Prediction(models.Model):
    class Choice(models.TextChoices):
        HOME = "home", "Home win"
        DRAW = "draw", "Draw"
        AWAY = "away", "Away win"
        NONE = "none", "No bet"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    choice = models.CharField(max_length=8, choices=Choice.choices, default=Choice.NONE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("player", "match")]

    def __str__(self) -> str:
        return f"{self.player.nick} / match {self.match.match_number}: {self.choice}"

    def points(self) -> int:
        if not self.match.is_scored:
            return 0
        if self.choice == self.Choice.NONE:
            return 1
        if self.choice == self.match.actual_outcome:
            return 3
        return 0


class DataSnapshot(models.Model):
    class Source(models.TextChoices):
        FIFA_SCHEDULE = "fifa_schedule", "FIFA schedule"
        FIFA_SCORES = "fifa_scores", "FIFA scores"
        OPENFOOTBALL = "openfootball", "OpenFootball"

    source = models.CharField(max_length=32, choices=Source.choices)
    url = models.URLField(blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    payload = models.TextField()
    content_type = models.CharField(max_length=120, blank=True)
    parsed_ok = models.BooleanField(default=False)
    parse_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-fetched_at"]


class SyncRun(models.Model):
    class Kind(models.TextChoices):
        IMPORT = "import", "Import"
        SCORE_SYNC = "score_sync", "Score sync"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_matches = models.PositiveIntegerField(default=0)
    conflict_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def finish(self, *, updated_matches: int = 0, conflict_count: int = 0, message: str = "", details: dict | None = None) -> None:
        self.finished_at = timezone.now()
        self.updated_matches = updated_matches
        self.conflict_count = conflict_count
        self.message = message
        if details is not None:
            self.details = details
        self.save(update_fields=["finished_at", "updated_matches", "conflict_count", "message", "details"])
