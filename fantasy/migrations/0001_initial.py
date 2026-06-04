import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DataSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("fifa_schedule", "FIFA schedule"), ("fifa_scores", "FIFA scores"), ("openfootball", "OpenFootball")], max_length=32)),
                ("url", models.URLField(blank=True)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.TextField()),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("parsed_ok", models.BooleanField(default=False)),
                ("parse_message", models.TextField(blank=True)),
            ],
            options={"ordering": ["-fetched_at"]},
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nick", models.SlugField(max_length=40, unique=True)),
                ("display_name", models.CharField(max_length=60)),
                ("pin_hash", models.CharField(max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["nick"]},
        ),
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("import", "Import"), ("score_sync", "Score sync")], max_length=16)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("updated_matches", models.PositiveIntegerField(default=0)),
                ("conflict_count", models.PositiveIntegerField(default=0)),
                ("message", models.TextField(blank=True)),
                ("details", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="Team",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("iso_code", models.CharField(blank=True, max_length=3)),
                ("flag", models.CharField(blank=True, max_length=8)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Venue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140, unique=True)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("timezone_name", models.CharField(blank=True, max_length=64)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="DeviceSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=128, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("user_agent", models.TextField(blank=True)),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to="fantasy.player")),
            ],
        ),
        migrations.CreateModel(
            name="Match",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("match_number", models.PositiveIntegerField(unique=True)),
                ("stage", models.CharField(choices=[("group", "Group"), ("round_of_32", "Round of 32"), ("round_of_16", "Round of 16"), ("quarter_final", "Quarter-final"), ("semi_final", "Semi-final"), ("third_place", "Third place"), ("final", "Final")], default="group", max_length=32)),
                ("group", models.CharField(blank=True, max_length=16)),
                ("round_label", models.CharField(blank=True, max_length=80)),
                ("kickoff_at", models.DateTimeField()),
                ("home_label", models.CharField(max_length=140)),
                ("away_label", models.CharField(max_length=140)),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("live", "Live"), ("final", "Final"), ("postponed", "Postponed")], default="scheduled", max_length=16)),
                ("home_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("away_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("source_payload", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("away_team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="away_matches", to="fantasy.team")),
                ("home_team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="home_matches", to="fantasy.team")),
                ("venue", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="fantasy.venue")),
            ],
            options={"ordering": ["kickoff_at", "match_number"]},
        ),
        migrations.CreateModel(
            name="Prediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("choice", models.CharField(choices=[("home", "Home win"), ("draw", "Draw"), ("away", "Away win"), ("none", "No bet")], default="none", max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="predictions", to="fantasy.match")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="predictions", to="fantasy.player")),
            ],
            options={"unique_together": {("player", "match")}},
        ),
    ]
