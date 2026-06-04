from django.urls import path

from . import views


urlpatterns = [
    path("", views.LandingView.as_view(), name="index"),
    path("join/", views.JoinView.as_view(), name="join"),
    path("matches/", views.MatchListView.as_view(), name="matches"),
    path("matches/<int:match_number>/", views.MatchDetailView.as_view(), name="match-detail"),
    path("matches/<int:match_number>/predict/", views.PredictionView.as_view(), name="predict"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("players/<slug:nick>/", views.PlayerDetailView.as_view(), name="player-detail"),
    path("bracket/", views.BracketView.as_view(), name="bracket"),
]
