from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fantasy.models import Match, Player, PortalSetting, Prediction
from fantasy.services.identity import GATE_PASSWORD_KEY, gate_cookie_value


class GateAndIdentityTests(TestCase):
    def test_first_gate_password_is_initialized_and_accepted(self):
        response = self.client.post(reverse("fantasy:index"), {"password": "first-secret"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.FANTASY_GATE_COOKIE, response.cookies)
        self.assertTrue(PortalSetting.objects.filter(key=GATE_PASSWORD_KEY).exists())

    def test_gate_rejects_wrong_password_after_initialization(self):
        PortalSetting.objects.create(key=GATE_PASSWORD_KEY, value=make_password("first-secret"))
        response = self.client.post(reverse("fantasy:index"), {"password": "bad"})
        self.assertEqual(response.status_code, 403)

    def test_initialized_gate_accepts_stored_password(self):
        PortalSetting.objects.create(key=GATE_PASSWORD_KEY, value=make_password("first-secret"))
        response = self.client.post(reverse("fantasy:index"), {"password": "first-secret"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.FANTASY_GATE_COOKIE, response.cookies)

    def test_register_sets_device_cookie_and_allows_prediction(self):
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        response = self.client.post(reverse("fantasy:join"), {"mode": "register", "nick": "Ana", "pin": "12"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.FANTASY_DEVICE_COOKIE, response.cookies)
        player = Player.objects.get(nick="ana")
        match = Match.objects.create(
            match_number=1,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Mexico",
            away_label="South Africa",
        )
        self.client.cookies[settings.FANTASY_DEVICE_COOKIE] = response.cookies[settings.FANTASY_DEVICE_COOKIE].value
        self.client.post(reverse("fantasy:predict", args=[match.match_number]), {"choice": "home"})
        self.assertEqual(Prediction.objects.get(player=player, match=match).choice, Prediction.Choice.HOME)

    def test_new_device_login_with_pin(self):
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        self.client.post(reverse("fantasy:join"), {"mode": "register", "nick": "Bob", "pin": "99"})
        self.client.cookies.clear()
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        response = self.client.post(reverse("fantasy:join"), {"mode": "login", "nick": "Bob", "pin": "99"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.FANTASY_DEVICE_COOKIE, response.cookies)

    def test_locked_match_rejects_prediction_change(self):
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        response = self.client.post(reverse("fantasy:join"), {"mode": "register", "nick": "Cat", "pin": "1"})
        self.client.cookies[settings.FANTASY_DEVICE_COOKIE] = response.cookies[settings.FANTASY_DEVICE_COOKIE].value
        match = Match.objects.create(
            match_number=2,
            kickoff_at=timezone.now() - timedelta(minutes=1),
            home_label="Brazil",
            away_label="Morocco",
        )
        response = self.client.post(reverse("fantasy:predict", args=[match.match_number]), {"choice": "home"})
        self.assertEqual(response.status_code, 403)

    def test_landing_page_shows_completed_matches_panel(self):
        Match.objects.create(
            match_number=1,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Mexico",
            away_label="South Africa",
        )
        Match.objects.create(
            match_number=2,
            kickoff_at=timezone.now() - timedelta(hours=1),
            home_label="Brazil",
            away_label="Morocco",
            status=Match.Status.FINAL,
            home_score=2,
            away_score=1,
        )

        response = self.client.get(reverse("fantasy:index"))

        self.assertContains(response, "Upcoming matches")
        self.assertContains(response, "Upcoming matches <span class=\"heading-note\">(1)</span>", html=True)
        self.assertContains(response, "Completed matches <span class=\"heading-note\">(1)</span>", html=True)
        self.assertContains(response, "Match 1")
        self.assertContains(response, "Match 2")

    def test_landing_match_summary_links_to_voting_detail(self):
        match = Match.objects.create(
            match_number=3,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Canada",
            away_label="USA",
        )

        response = self.client.get(reverse("fantasy:index"))

        self.assertContains(response, reverse("fantasy:match-detail", args=[match.match_number]))

    def test_landing_page_shows_match_times_in_cet(self):
        Match.objects.create(
            match_number=3,
            kickoff_at=datetime(2026, 6, 11, 19, 0, tzinfo=dt_timezone.utc),
            home_label="Canada",
            away_label="USA",
        )

        response = self.client.get(reverse("fantasy:index"))

        self.assertContains(response, "Jun 11, 21:00 CET")

    def test_landing_leaders_show_preliminary_max_based_on_scored_matches(self):
        Player.objects.create(nick="ana", display_name="Ana", pin_hash="x")
        Match.objects.create(
            match_number=3,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Canada",
            away_label="USA",
        )

        response = self.client.get(reverse("fantasy:index"))

        # No scored matches yet, so max is 0
        self.assertContains(response, "Leaders <span class=\"heading-note\">(max 0)</span>", html=True)
        self.assertContains(response, "<strong>0</strong>", html=True)
        self.assertNotContains(response, "<strong>0 (0-3)</strong>", html=True)

    def test_landing_page_allows_quick_vote_for_logged_in_player(self):
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        response = self.client.post(reverse("fantasy:join"), {"mode": "register", "nick": "Dan", "pin": "12"})
        self.client.cookies[settings.FANTASY_DEVICE_COOKIE] = response.cookies[settings.FANTASY_DEVICE_COOKIE].value
        match = Match.objects.create(
            match_number=3,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Canada",
            away_label="USA",
        )

        response = self.client.get(reverse("fantasy:index"))

        self.assertContains(response, reverse("fantasy:predict", args=[match.match_number]))
        self.assertContains(response, 'name="choice" value="home"')
        self.assertContains(response, 'name="choice" value="draw"')
        self.assertContains(response, 'name="choice" value="away"')
        self.assertContains(response, 'name="choice" value="none"')
        self.assertContains(response, 'fantasy/flags/ca.svg')
        self.assertContains(response, 'fantasy/flags/us.svg')

    def test_match_detail_shows_voting_form(self):
        self.client.cookies[settings.FANTASY_GATE_COOKIE] = gate_cookie_value()
        response = self.client.post(reverse("fantasy:join"), {"mode": "register", "nick": "Eve", "pin": "12"})
        self.client.cookies[settings.FANTASY_DEVICE_COOKIE] = response.cookies[settings.FANTASY_DEVICE_COOKIE].value
        match = Match.objects.create(
            match_number=4,
            kickoff_at=timezone.now() + timedelta(hours=1),
            home_label="Brazil",
            away_label="Morocco",
        )

        response = self.client.get(reverse("fantasy:match-detail", args=[match.match_number]))

        self.assertContains(response, "Match 4")
        self.assertContains(response, reverse("fantasy:predict", args=[match.match_number]))
        self.assertContains(response, 'name="choice" value="home"')
