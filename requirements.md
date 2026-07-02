# FIFA WC 2026 Fantasy Portal Requirements

Last updated: 2026-06-04

## Product Summary

Build and maintain a standalone public FIFA World Cup 2026 fantasy prediction portal at `https://ulkas.duckdns.org/fantasy`.

The portal displays World Cup 2026 matches, groups, timelines, venue/time metadata, and knockout plans. Users can join with a lightweight nick+PIN identity and submit fantasy predictions for matches.

## Core User Flow

- Visitors can see the public landing page.
- On first run, the first non-empty password submitted on the landing page is hashed, stored in the database, and becomes the shared portal entry password.
- After the entry password is initialized, visitors must provide that shared portal password to enter further.
- After the password is accepted, a long-lived cookie is stored and the same device should not ask for that password again.
- A visitor then registers a unique nick plus PIN, or logs in on a new device with the same nick+PIN.
- After nick+PIN setup, a long-lived device cookie is stored and the same device should not ask again.
- Users are never logged out by the UI. There is no logout option.

## Tournament Data

- Store match schedule data offline after first import.
- Show countries and flags, not player rosters.
- Every match stores at least:
  - match number
  - stage/group
  - kickoff time
  - venue/location
  - home/away team or placeholder label
  - status
  - score when available
- Group-stage and knockout/playoff timeline views must be available.
- The app must support unresolved playoff placeholders until teams are known.

## Data Sources And Sync

- Use free-only data sources.
- Use FIFA public pages as the canonical official source for schedule/results snapshots.
- Use OpenFootball World Cup JSON as the structured seed and cross-check source.
- Store raw source snapshots before parsing so data can be audited and reprocessed offline.
- `import_schedule` performs the first schedule import.
- `sync_scores` refreshes scores and records sync audit data.
- Score sync is intended to run hourly via Docker/VPS cron.
- Conflicting final scores must be recorded and must not silently overwrite already-final stored results.

## Betting Rules

- Users may bet any match or choose not to bet.
- Users may skip a match entirely; missing prediction counts like no bet once the match is scored.
- Upcoming matches can be changed multiple times.
- Bets lock at scheduled kickoff.
- Started, live, final, or past-kickoff matches cannot be changed.
- Scoring:
  - Correct home/away win prediction: 3 points.
  - Correct draw prediction: 3 points.
  - No bet or missing bet on a scored match: 1 point.
  - Wrong prediction: 0 points.
  - For knockout matches, prediction settlement uses the regular-time result only; extra-time wins and penalty shootouts both settle as draws.
- Unscored matches contribute 0 points until final.

## Main Views

- Landing page:
  - rules summary
  - password gate when not unlocked
  - short upcoming match list
  - short leaders list
- Join/login page:
  - register nick+PIN
  - login with existing nick+PIN
- Matches page:
  - full timeline grouped by groups and knockout stages
  - country flags and names
  - kickoff, venue, status, score
  - prediction controls for editable matches where country tiles can be clicked directly to submit a home/away win
- Leaderboard page:
  - current user ranking
  - points and useful tie-break context
- Player detail page:
  - selected user prediction list and points per match using the same split match UI and picked markers as the betting list
- Bracket page:
  - playoff/knockout plan with placeholders when teams are unresolved
  - connected bracket layout with visible connector lines between rounds
  - horizontal scrolling for wide knockout layouts

## UI Direction

- Use a compact tournament dashboard style inspired by:
  - `https://www.score7.io/tournaments/template-wc2026/overview`
  - `https://www.score7.io/tools/world-cup-2026`
- Use the mirrored Kyberia favicon from `https://kyberia.sk/favicon.ico`.
- Use the mirrored portal logo from `https://wave.rozhlas.cz/sites/default/files/images/02052125.png`.
- Favor match rows, group blocks, flag-first country display, Score7-inspired dark dashboard colors, green accents, and bracket-style playoff layout.
- Center later knockout rounds between the related cells from previous rounds where practical.
- Split each match visually into home and away country regions with prominent flags and distinct backgrounds.
- Show the selected prediction with a strong filled state and explicit picked marker.
- Use the same picked-state treatment for read-only player prediction history.
- The first screen should be the usable portal, not a marketing landing page.
- Keep the UI responsive for desktop and mobile.

## Technical Requirements

- Standalone Django project in `C:\develop\code\python\wcf`.
- Canonical GitHub remote is `git@github.com:ulkas/fifawc.fantasybet.git`.
Git operations for this project must use the personal `ulkas` GitHub identity only. Never use corporate GitHub credentials
- Before any Git operation, verify the repo-local identity and auth path are configured for `ulkas`.
- Use Docker for all local development and production-like commands.
- Do not install dependencies on the host.
- Do not run host Python, pip, Django, or database tools for this project.
- Local app runs through Docker Compose.
- Production uses the same shape as neighboring projects:
  - Django 5.1
  - PostgreSQL
  - Gunicorn
  - Nginx
  - Docker Compose
  - shared VPS Traefik routing
  - DuckDNS host `ulkas.duckdns.org`
  - path prefix `/fantasy`
- Keep app cookies scoped to `/fantasy`.
- Deployment scripts must not hardcode concrete server IP addresses, login targets, tokens, or local SSH private-key paths; use ignored env/GitHub secrets.
- Deployment must mirror the neighboring AWW GitHub Actions pipeline: pushes to `main` run `.github/workflows/deploy.yml`, use `scripts/deploy.ps1` in archive-copy mode, deploy to `/opt/wcf`, and postcheck `https://ulkas.duckdns.org/fantasy/`.
- GitHub production environment must provide `DEPLOY_HOST`, `DEPLOY_SSH_PRIVATE_KEY`, and `DEPLOY_KNOWN_HOSTS`; optional environment secrets may override non-sensitive deployment defaults.

## Security Model

- The portal is intentionally low security.
- The shared portal entry password is initialized through the first landing-page submission and stored only as a server-side hash.
- PINs and persistent device tokens must still be hashed server-side.
- Shared password and device cookies are long-lived by design.
- Do not add complex identity providers unless explicitly requested.
- Preserve CSRF protection for form posts.

## Testing Requirements

- Maintain tests for:
  - scoring rules
  - no-bet and missing prediction scoring
  - kickoff locking
  - password gate
  - nick+PIN registration/login
  - device persistence
  - schedule import from offline fixture
  - score sync idempotency/conflict behavior
- Run tests through Docker:

```powershell
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
```

## Documentation Requirements

- Update this file as soon as product behavior, UX, data flow, deployment, commands, or constraints change.
- Update relevant docs in `docs/` and `README.md` in the same change as code.
- Documentation must stay aligned with the implemented behavior, not planned behavior.

## Changelog

- 2026-06-04: Initial requirements captured from the product request and implemented v1 portal behavior.
- 2026-06-04: Added AWW-style GitHub Actions/archive-copy production deployment pipeline for `fifawc.fantasybet`.
- 2026-06-04: Added canonical GitHub repository and mandatory `ulkas`-only Git identity requirements.
- 2026-06-04: Updated match prediction UX so country regions are prominent clickable voting targets.
- 2026-06-04: Replaced static entry password with first-run database initialization of the shared entry password.
- 2026-06-04: Redacted deployment script defaults so host and SSH key values come from ignored env/secrets.
