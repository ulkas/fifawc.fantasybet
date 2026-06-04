# Development Agent

Use this agent guidance for implementation work in the WC 2026 fantasy portal.

## Operating Rules

- Work only inside `C:\develop\code\python\wcf` unless the user explicitly asks otherwise.
- Before any Git operation, verify this repo is configured for the personal `ulkas` GitHub identity, not `lukas-trojcak-tfs`.
- Expected Git remote is `git@github.com:ulkas/fifawc.fantasybet.git`.
- Expected repo-local Git identity is `user.name=ulkas` and `user.email=ulkas@users.noreply.github.com`.
- Expected repo-local SSH command uses ignored `.git-auth/` key material without exposing the concrete private-key path.
- Do not change global Git configuration.
- Use Docker Compose for all runtime checks and Django commands.
- Never use host Python, host pip, host Django commands, or host database clients.
- Do not install dependencies on the host.
- If Docker daemon access is blocked, request escalation for the Docker command.

## Required Reading Before Changes

- `requirements.md`
- `README.md`
- Relevant files under `docs/`
- Existing models/views/tests for the subsystem being changed

## Required Documentation Updates

Update docs immediately when behavior changes:

- `requirements.md` for product behavior, scoring, auth, data, UX, or constraints.
- `README.md` for developer/operator commands.
- `docs/` for deployment, data source, sync, or architecture changes.

Do not finish a change while docs describe old behavior.

## Testing

Use Dockerized commands only:

```powershell
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py check
```

Add or update tests when changing:

- shared entry password initialization or gate behavior
- scoring
- prediction locking
- registration/login/device cookies
- schedule import
- score sync
- match data model
- leaderboard/player detail behavior
