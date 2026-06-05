"""
Simulation command: sets match results and dates for testing scoring and leaderboard display.
Usage:
  docker-compose exec -T web python manage.py simulate_matches setup    # Activate simulation
  docker-compose exec -T web python manage.py simulate_matches restore  # Restore to current state
"""

from datetime import timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from fantasy.models import Match, PortalSetting


class Command(BaseCommand):
    help = "Simulate match results and dates for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            type=str,
            choices=["setup", "restore"],
            help="setup to activate simulation, restore to revert to current state",
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "setup":
            self.setup_simulation()
        elif action == "restore":
            self.restore_simulation()

    def setup_simulation(self):
        """Set matches to final with scores, dates to FIFA schedule (June 11-25)"""
        # Save current state for restoration
        current_state = {
            "match_1": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_2": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_3": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_4": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_5": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_6": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
            "match_7": {"status": None, "home_score": None, "away_score": None, "kickoff_at": None},
        }

        try:
            # Get the current date at UTC
            base_date = timezone.now()
            
            # Matchday 1 (June 11-12)
            # Match 1: Thursday 11 June, 21:00 CET = 19:00 UTC
            june_11_2100_utc = base_date.replace(year=2026, month=6, day=11, hour=19, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            # Match 2: Friday 12 June, 04:00 CET = 02:00 UTC
            june_12_0400_utc = base_date.replace(year=2026, month=6, day=12, hour=2, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            # Match 7 (Group B): Friday 12 June, 21:00 CET = 19:00 UTC
            june_12_2100_utc = base_date.replace(year=2026, month=6, day=12, hour=19, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            
            # Matchday 2 (June 18-19)
            # Match 3: Thursday 18 June, 18:00 CET = 16:00 UTC
            june_18_1800_utc = base_date.replace(year=2026, month=6, day=18, hour=16, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            # Match 4: Friday 19 June, 03:00 CET = 01:00 UTC
            june_19_0300_utc = base_date.replace(year=2026, month=6, day=19, hour=1, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            
            # Matchday 3 (June 25)
            # Match 5: Thursday 25 June, 03:00 CET = 01:00 UTC
            june_25_0300_utc = base_date.replace(year=2026, month=6, day=25, hour=1, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc)
            
            # Match 1: Mexico 3 - 1 South Africa (home win)
            match1 = Match.objects.get(match_number=1)
            current_state["match_1"]["status"] = match1.status
            current_state["match_1"]["home_score"] = match1.home_score
            current_state["match_1"]["away_score"] = match1.away_score
            current_state["match_1"]["kickoff_at"] = match1.kickoff_at
            
            match1.status = Match.Status.FINAL
            match1.home_score = 3
            match1.away_score = 1
            match1.kickoff_at = june_11_2100_utc
            match1.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Match 1: Mexico 3 - 1 South Africa (Jun 11, 21:00 CET)"))

            # Match 2: South Korea 1 - 2 Czech Republic (away win)
            match2 = Match.objects.get(match_number=2)
            current_state["match_2"]["status"] = match2.status
            current_state["match_2"]["home_score"] = match2.home_score
            current_state["match_2"]["away_score"] = match2.away_score
            current_state["match_2"]["kickoff_at"] = match2.kickoff_at
            
            match2.status = Match.Status.FINAL
            match2.home_score = 1
            match2.away_score = 2
            match2.kickoff_at = june_12_0400_utc
            match2.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Match 2: South Korea 1 - 2 Czech Republic (Jun 12, 04:00 CET)"))



            

            # Match 7 (Group B): Canada 1 - 1 Bosnia & Herzegovina (draw)
            match7 = Match.objects.get(match_number=7)
            current_state["match_7"]["status"] = match7.status
            current_state["match_7"]["home_score"] = match7.home_score
            current_state["match_7"]["away_score"] = match7.away_score
            current_state["match_7"]["kickoff_at"] = match7.kickoff_at
            
            match7.status = Match.Status.FINAL
            match7.home_score = 1
            match7.away_score = 1
            match7.kickoff_at = june_12_2100_utc
            match7.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Match 7: Canada 1 - 1 Bosnia & Herzegovina (Jun 12, 21:00 CET)"))

            # Save state for restoration
            PortalSetting.objects.update_or_create(
                key="simulation_state",
                defaults={"value": str(current_state)},
            )

            self.stdout.write(self.style.SUCCESS("\n✅ Simulation activated with FIFA schedule (Jun 11-25)"))
            self.stdout.write(f"   Restore with: python manage.py simulate_matches restore\n")

        except Match.DoesNotExist as e:
            raise CommandError(f"Match not found: {e}")

    def restore_simulation(self):
        """Restore matches to scheduled state"""
        try:
            for match_num in [1, 2, 3, 4, 5, 6, 7]:
                match = Match.objects.get(match_number=match_num)
                match.status = Match.Status.SCHEDULED
                match.home_score = None
                match.away_score = None
                match.save()
                self.stdout.write(self.style.SUCCESS(f"✓ Match {match_num} restored to scheduled"))

            PortalSetting.objects.filter(key="simulation_state").delete()
            self.stdout.write(self.style.SUCCESS("\n✅ Simulation deactivated, restored to current state\n"))

        except Match.DoesNotExist as e:
            raise CommandError(f"Match not found: {e}")
