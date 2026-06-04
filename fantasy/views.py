from __future__ import annotations

from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .forms import GateForm, JoinForm, PredictionForm
from .models import Match, Player, Prediction
from .services.identity import (
    attach_player_device,
    authenticate_player,
    create_player,
    gate_cookie_value,
    get_current_player,
    has_gate,
    is_gate_password_configured,
    set_long_cookie,
    verify_or_initialize_gate_password,
)
from .services.scoring import player_prediction_rows, ranking_rows, score_range


def require_gate(view_func):
    def wrapped(self, request, *args, **kwargs):
        if not has_gate(request):
            return redirect("fantasy:index")
        return view_func(self, request, *args, **kwargs)

    return wrapped


def require_player(view_func):
    def wrapped(self, request, *args, **kwargs):
        if not has_gate(request):
            return redirect("fantasy:index")
        if get_current_player(request) is None:
            return redirect("fantasy:join")
        return view_func(self, request, *args, **kwargs)

    return wrapped


class LandingView(View):
    template_name = "fantasy/index.html"

    def get(self, request):
        context = self.context(request, gate_form=GateForm())
        return render(request, self.template_name, context)

    def post(self, request):
        form = GateForm(request.POST)
        if not form.is_valid() or not verify_or_initialize_gate_password(form.cleaned_data["password"]):
            messages.error(request, "Password is not valid.")
            return render(request, self.template_name, self.context(request, gate_form=form), status=403)
        response = redirect("fantasy:join")
        set_long_cookie(response, settings.FANTASY_GATE_COOKIE, gate_cookie_value())
        return response

    def context(self, request, gate_form):
        now = timezone.now()
        current_player = get_current_player(request)
        upcoming_queryset = Match.objects.filter(kickoff_at__gte=now, status__in=[Match.Status.SCHEDULED, Match.Status.LIVE])
        completed_queryset = Match.objects.filter(status=Match.Status.FINAL)
        upcoming_matches = list(upcoming_queryset.select_related("home_team", "away_team", "venue")[:3])
        completed_matches = list(completed_queryset.select_related("home_team", "away_team", "venue").order_by("-kickoff_at", "-match_number")[:3])
        
        all_match_ids = [m.id for m in upcoming_matches + completed_matches]
        predictions = {}
        if current_player is not None:
            predictions = {
                prediction.match_id: prediction
                for prediction in Prediction.objects.filter(player=current_player, match_id__in=all_match_ids)
            }
        
        return {
            "gate_open": has_gate(request),
            "gate_configured": is_gate_password_configured(),
            "gate_form": gate_form,
            "upcoming_rows": [
                {"match": match, "prediction": predictions.get(match.id)}
                for match in upcoming_matches
            ],
            "upcoming_match_count": upcoming_queryset.count(),
            "completed_match_count": completed_queryset.count(),
            "completed_matches_with_predictions": [
                {"match": match, "prediction": predictions.get(match.id)}
                for match in completed_matches
            ],
            "leaders": ranking_rows(),
            "score_range": score_range(),
        }


class JoinView(View):
    template_name = "fantasy/join.html"

    @require_gate
    def get(self, request):
        if get_current_player(request):
            return redirect("fantasy:matches")
        return render(request, self.template_name, {"form": JoinForm(initial={"mode": "register"})})

    @require_gate
    def post(self, request):
        form = JoinForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)
        mode = form.cleaned_data["mode"]
        nick = form.cleaned_data["nick"]
        pin = form.cleaned_data["pin"]
        if mode == "register":
            try:
                player = create_player(nick, pin)
            except IntegrityError:
                messages.error(request, "That nick already exists. Use login instead.")
                return render(request, self.template_name, {"form": form}, status=409)
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(request, self.template_name, {"form": form}, status=400)
        else:
            player = authenticate_player(nick, pin)
            if player is None:
                messages.error(request, "Nick or PIN is not valid.")
                return render(request, self.template_name, {"form": form}, status=403)
        response = redirect("fantasy:matches")
        attach_player_device(response, request, player)
        return response


class MatchListView(View):
    template_name = "fantasy/matches.html"

    @require_player
    def get(self, request):
        player = get_current_player(request)
        predictions = {prediction.match_id: prediction for prediction in Prediction.objects.filter(player=player)}
        groups = defaultdict(list)
        knockouts = []
        for match in Match.objects.select_related("home_team", "away_team", "venue"):
            row = {"match": match, "prediction": predictions.get(match.id)}
            if match.stage == Match.Stage.GROUP:
                groups[match.group or "Group stage"].append(row)
            else:
                knockouts.append(row)
        return render(
            request,
            self.template_name,
            {
                "groups": dict(groups),
                "knockouts": knockouts,
                "prediction_choices": Prediction.Choice,
            },
        )


class MatchDetailView(View):
    template_name = "fantasy/match_detail.html"

    @require_player
    def get(self, request, match_number: int):
        player = get_current_player(request)
        match = get_object_or_404(
            Match.objects.select_related("home_team", "away_team", "venue"),
            match_number=match_number,
        )
        prediction = Prediction.objects.filter(player=player, match=match).first()
        return render(request, self.template_name, {"match": match, "prediction": prediction})


class PredictionView(View):
    @require_player
    def post(self, request, match_number: int):
        player = get_current_player(request)
        match = get_object_or_404(Match, match_number=match_number)
        if match.is_locked:
            return HttpResponseForbidden("This match is locked.")
        form = PredictionForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Choose a valid prediction.")
            return redirect("fantasy:matches")
        Prediction.objects.update_or_create(
            player=player,
            match=match,
            defaults={"choice": form.cleaned_data["choice"]},
        )
        messages.success(request, f"Prediction saved for match {match.match_number}.")
        return HttpResponseRedirect(request.POST.get("next") or reverse("fantasy:matches"))


class LeaderboardView(View):
    template_name = "fantasy/leaderboard.html"

    @require_gate
    def get(self, request):
        return render(request, self.template_name, {"leaders": ranking_rows(), "score_range": score_range()})


class PlayerDetailView(View):
    template_name = "fantasy/player_detail.html"

    @require_gate
    def get(self, request, nick: str):
        player = get_object_or_404(Player, nick=nick)
        rows = player_prediction_rows(player)
        return render(request, self.template_name, {"profile_player": player, "rows": rows})


class BracketView(View):
    template_name = "fantasy/bracket.html"

    @require_gate
    def get(self, request):
        stages = defaultdict(list)
        for match in Match.objects.exclude(stage=Match.Stage.GROUP).select_related("venue"):
            stages[match.get_stage_display()].append(match)
        return render(request, self.template_name, {"stages": dict(stages)})
