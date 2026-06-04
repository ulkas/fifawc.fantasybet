from django.contrib import admin

from .models import DataSnapshot, DeviceSession, Match, Player, PortalSetting, Prediction, SyncRun, Team, Venue


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("nick", "created_at", "last_seen_at")
    search_fields = ("nick",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "iso_code", "flag")
    search_fields = ("name", "iso_code")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country")
    search_fields = ("name", "city", "country")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("match_number", "stage", "group", "kickoff_at", "home_label", "away_label", "status", "score_label")
    list_filter = ("stage", "group", "status")
    search_fields = ("home_label", "away_label", "venue__name")


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("player", "match", "choice", "updated_at")
    list_filter = ("choice",)
    search_fields = ("player__nick",)


admin.site.register(DeviceSession)
admin.site.register(PortalSetting)
admin.site.register(DataSnapshot)
admin.site.register(SyncRun)
