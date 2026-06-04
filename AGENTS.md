# Agent Instructions

## Project Mission

Build and maintain the standalone FIFA World Cup 2026 fantasy tournament portal in this workspace.

The target production URL is:

```text
https://ulkas.duckdns.org/fantasy
```

## Hard Constraints

- Canonical Git remote is `git@github.com:ulkas/fifawc.fantasybet.git`.
- Git operations must always use the personal GitHub user `ulkas`.
- Never use corporate GitHub credentials, or the global Windows company Git identity for this repository.
- Before every Git operation, verify repo-local Git identity and SSH configuration:

```powershell
git config --get user.name
git config --get user.email
git config --get core.sshCommand
git remote -v
```

- Expected local identity:
  - `user.name=ulkas`
  - `user.email=ulkas@users.noreply.github.com`
  - `origin=git@github.com:ulkas/fifawc.fantasybet.git`
  - `core.sshCommand` points to ignored `.git-auth/` key material without exposing a concrete private-key path
- Keep Git auth isolated to repo-local config. Do not change global Git config, global SSH keys, or shared credential helpers.
- `.git-auth/` contains secret key material and must remain ignored.
- Do not commit concrete deploy host IPs, login targets, tokens, private key paths, or other deployment secrets. Use ignored env files or GitHub Environment secrets.
- Use Docker for all local development.
- Do not install project dependencies on the host.
- Do not run host Python, pip, Django, or database tools for this project.
- Run Django commands through Docker Compose, for example:

```powershell
docker-compose exec -T web python manage.py check
docker-compose exec -T web python manage.py import_schedule
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
```

- Keep the app standalone in `C:\develop\code\python\wcf`.
- Do not move it into the neighboring `www` project.
- Preserve production path-prefix routing on `/fantasy`.
- Keep session and CSRF cookies scoped to `/fantasy`.
- Do not introduce a third-party identity provider unless explicitly requested.

## Product Rules

- Public landing page, then shared password gate.
- On first run, the first non-empty password submitted at the gate becomes the shared entry password.
- Store the shared entry password only as a server-side hash.
- Long-lived gate cookie after successful password entry.
- Player identity is nick+PIN.
- PINs and device tokens must be hashed server-side.
- Long-lived device cookie after successful register/login.
- No logout UI.
- Users can edit predictions until scheduled kickoff.
- Past, live, started, or final matches are locked.
- Correct win/draw prediction scores 3 points.
- No bet or missing bet scores 1 point after the match is scored.
- Wrong prediction scores 0 points.

## Data Rules

- Use free-only data sources.
- Store source snapshots before parsing.
- Treat FIFA public pages as canonical official snapshots.
- Use OpenFootball JSON as the structured seed/cross-check source.
- Preserve offline fixtures for repeatable tests.
- Hourly score sync should be runnable as a Dockerized management command.
- Do not silently overwrite conflicting final scores; record conflicts.

## Documentation Workflow

- Always update `requirements.md` as soon as requirements, product behavior, UX, data model, scoring, commands, deployment, or constraints change.
- Always update `README.md` and relevant `docs/` files in the same change when behavior or operations change.
- Documentation must describe the current implemented system.
- If a code change creates a mismatch with docs or requirements, fix the docs before finishing.

## Development Workflow

- Prefer small, scoped changes.
- Keep tests aligned with risk.
- Use existing Django patterns in this repo.
- Add migrations for model changes.
- Keep generated/local files out of images and commits using `.gitignore` and `.dockerignore`.
- When using browser verification, prefer the in-app browser for local UI smoke checks.

## Verification

For meaningful changes, run the relevant Dockerized checks:

```powershell
docker-compose config
docker-compose -f docker-compose.prod.yml config
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py check
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
```

If Docker access requires elevated permissions in this environment, request approval rather than using host tools.
