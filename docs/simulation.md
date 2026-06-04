# Match Simulation Mechanism

The simulation mechanism allows you to test scoring, predictions, and leaderboard functionality by activating match results without modifying permanent data.

## Purpose

The simulator is useful for:

- **Testing scoring logic** with real match data before production
- **Demonstrating leaderboard and prediction UI** with completed matches
- **Verifying visual indicators** (correct/wrong predictions, point calculations)
- **Integration testing** of the entire prediction lifecycle

## Usage

### Activate Simulation

```powershell
docker-compose exec -T web python manage.py simulate_matches setup
```

This activates two completed matches with scores:
- **Match 1**: Mexico 3 - 1 South Africa (June 11, 21:00 UTC) - Home win
- **Match 2**: South Korea 1 - 2 Czech Republic (June 12, 04:00 UTC) - Away win

### Restore Current State

```powershell
docker-compose exec -T web python manage.py simulate_matches restore
```

This immediately reverts both matches to `SCHEDULED` status with no scores, restoring the original state.

## How It Works

### Data Modifications

When `setup` is called, the command:

1. **Sets match status to FINAL** - Makes matches appear as completed
2. **Adds scores** - Populates `home_score` and `away_score` fields
3. **Updates kickoff times to past dates** - June 11-12, 2026 (before the current simulated date of June 4)
4. **Saves backup state** - Stores original values in `PortalSetting` table for restoration

### Filtering Logic

The app filters matches based on status and kickoff time:

```python
# Upcoming matches: scheduled or live, with future kickoff times
upcoming = Match.objects.filter(
    kickoff_at__gte=now,
    status__in=[Match.Status.SCHEDULED, Match.Status.LIVE]
)

# Completed matches: final status with scored results
completed = Match.objects.filter(status=Match.Status.FINAL)
```

This ensures:
- Completed matches appear in the "Completed matches" section, not upcoming
- Scores are displayed only for final matches
- Visual prediction indicators show match outcomes

### Prediction Scoring

Once a match is final with scores:

```python
def points_for(player, match, prediction):
    if not match.is_scored:
        return 0
    if prediction is None or prediction.choice == "none":
        return 1  # No bet scores 1 point
    if prediction.choice == match.actual_outcome:
        return 3  # Correct prediction scores 3 points
    return 0      # Wrong prediction scores 0 points
```

The leaderboard recalculates automatically without any manual action.

## Visual Indicators

The UI displays prediction correctness with color coding:

| Indicator | Meaning | Color |
|-----------|---------|-------|
| **Correct Bet** | Prediction matched actual outcome | Green (`#5fb34a`) |
| **Wrong Bet** | Prediction did not match outcome | Red-brown (`#8f4d44`) |
| **No Bet** | Did not place a bet before kickoff | Gray (`#757575`) |

These indicators appear in:
- **Homepage completed matches** - Summary cards show highlighted correct predictions
- **Player detail page** - Full match readout with scored predictions
- **Leaderboard** - Player point totals reflect the scored matches

## Test Scenarios

### Scenario 1: Correct Home Win Prediction

1. Activate simulation (`setup`)
2. Check if player who predicted "Mexico home win" shows green highlight
3. Verify leaderboard shows +3 points
4. Run `restore` and verify state returns

### Scenario 2: Mixed Predictions

With the simulation active, a player can:
- Get +3 points for correct Mexico home win prediction
- Get 0 points for wrong South Korea prediction (if they predicted home instead of away)
- Get +1 point for not betting on a match that finished

### Scenario 3: No Bet Handling

If a player placed no prediction on a scored match:
- Shows "No bet" with gray indicator
- Awards +1 point (participation bonus)

## Implementation Files

- **Command**: [fantasy/management/commands/simulate_matches.py](../fantasy/management/commands/simulate_matches.py)
  - Handles setup and restore logic
  - Manages state backup and recovery

- **Views**: [fantasy/views.py](../fantasy/views.py)
  - LandingView: Filters matches by status and time
  - Loads predictions alongside matches

- **Templates**:
  - [fantasy/templates/fantasy/partials/match_summary.html](../fantasy/templates/fantasy/partials/match_summary.html) - Shows scores and visual indicators
  - [fantasy/templates/fantasy/player_detail.html](../fantasy/templates/fantasy/player_detail.html) - Displays full prediction results with scoring
  - [fantasy/templates/fantasy/index.html](../fantasy/templates/fantasy/index.html) - Separates upcoming/completed sections

- **Services**: [fantasy/services/scoring.py](../fantasy/services/scoring.py)
  - Calculates points based on match outcomes
  - Generates ranking rows with prediction stats

## Limitations

- **Two matches only**: Simulation currently handles only matches 1 and 2
- **No state file on disk**: Backup stored in database, not persisted between container restarts
- **Manual expansion needed**: To add more matches, edit the `setup_simulation()` method

## Extension

To simulate additional matches, add them to the setup command:

```python
match3 = Match.objects.get(match_number=3)
match3.status = Match.Status.FINAL
match3.home_score = 2
match3.away_score = 0
match3.kickoff_at = base_date.replace(month=6, day=13, hour=21, minute=0)
match3.save()
```

Then add restoration logic in the `restore_simulation()` method.
