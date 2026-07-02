# FIFA WC 2026 Fantasy Portal

Standalone Django portal for FIFA World Cup 2026 match predictions.

## Local Development

Use Docker for all local development. Do not install dependencies on the host and do not run host Python, pip, Django, or database tools for this project.

```powershell
docker-compose up -d --build
docker-compose exec -T web python manage.py import_schedule --skip-remote-fifa --openfootball-file tests/fixtures_openfootball.json
```

Open `http://localhost:8086`.

On a fresh database, the first password submitted on the landing page becomes the shared portal entry password. The app stores that password as a server-side hash, not in environment variables.

## Commands

- `python manage.py import_schedule`: stores FIFA/OpenFootball source snapshots and imports the schedule.
- `python manage.py sync_scores`: refreshes final scores from configured free structured sources.
- `python manage.py recompute_scores`: prints the current ranking.
- `python manage.py simulate_matches setup`: activates test match results for demonstration and testing.
- `python manage.py simulate_matches restore`: reverts simulation and restores original state.

Run every app command through the container in normal development and production:

```powershell
docker-compose exec -T web python manage.py test
docker-compose exec -T web python manage.py check
docker-compose exec -T web python manage.py import_schedule
docker-compose exec -T web python manage.py sync_scores
docker-compose exec -T web python manage.py simulate_matches setup
```

See [simulation.md](docs/simulation.md) for detailed simulation documentation.

## Prediction UI

Editable matches use split home/draw/away voting regions. Clicking a country tile submits that country as the match winner prediction; draw and no-bet remain separate choices. The selected option is shown as a filled tile with a picked badge. Player pages reuse the same visual treatment in read-only form.

Knockout predictions settle against the score at the end of regular time. Extra-time winners and penalty shootouts are both graded as draws for fantasy scoring.

## Bracket UI

The bracket page renders knockout rounds as connected columns with offset spacing and connector lines so later rounds visually sit between their feeder matches. Wide brackets scroll horizontally with a visible scrollbar.

## Visual Style

The UI uses a Score7-inspired dark tournament dashboard palette with green accents, subdued panels, and high-contrast match rows.

## Static Assets

The site favicon is mirrored from `https://kyberia.sk/favicon.ico`.
The portal logo is mirrored from `https://wave.rozhlas.cz/sites/default/files/images/02052125.png`.

## Production

Production is designed for the shared VPS reverse proxy at:

```text
https://ulkas.duckdns.org/fantasy
```

Use `.env.production.example` as the starting point and keep app-specific cookie/path settings on `/fantasy`.

The shared entry password is not configured in env. On first production run, the first submitted gate password initializes it in the database.

Deployment mirrors the neighboring AWW project:

- Pushes to `main` run `.github/workflows/deploy.yml`.
- The workflow deploys through `scripts/deploy.ps1` in `archive-copy` mode.
- Required GitHub Environment secrets: `DEPLOY_HOST`, `DEPLOY_SSH_PRIVATE_KEY`, and `DEPLOY_KNOWN_HOSTS`.
- `DEPLOY_HOST` and SSH key material must come from ignored local env or GitHub Environment secrets, not committed defaults.
- Default app directory: `/opt/wcf`.

See [deployment.md](docs/deployment.md) and [deployment-agent.md](docs/deployment-agent.md).

## Git

Canonical remote:

```text
git@github.com:ulkas/fifawc.fantasybet.git
```

Git operations for this project must use the personal `ulkas` GitHub identity only. Never use corporate GitHub credentials. Verify repo-local Git identity before Git work:

```powershell
git config --get user.name
git config --get user.email
git config --get core.sshCommand
git remote -v
```
