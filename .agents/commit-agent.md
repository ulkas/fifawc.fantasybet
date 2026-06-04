# Commit Agent

Use this guidance when preparing commits for the WC 2026 fantasy portal.

## Pre-Commit Checks

- Before any Git command, verify repo-local Git identity is `ulkas`, not the company user:

```powershell
git config --get user.name
git config --get user.email
git config --get core.sshCommand
git remote -v
```

- Expected remote: `git@github.com:ulkas/fifawc.fantasybet.git`.
- Expected user: `ulkas <ulkas@users.noreply.github.com>`.
- Expected SSH key material lives under ignored `.git-auth/`; do not commit or name concrete private-key paths.
- Do not change global Git config and never use `lukas-trojcak-tfs`.
- Confirm code, tests, docs, and requirements are synchronized.
- Verify `requirements.md` reflects current product behavior.
- Verify `README.md` and `docs/` reflect current commands and deployment shape.
- Ensure local/generated files such as `.env`, `.env.production`, `staticfiles/`, and database files are not committed.

## Docker-Only Rule

All verification must use Docker Compose. Do not use host Python, pip, Django, or database tools.

Recommended checks:

```powershell
docker-compose config
docker-compose -f docker-compose.prod.yml config
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py check
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
```

## Commit Content

- Keep commits scoped.
- Include migrations with model changes.
- Include tests for behavior changes.
- Include docs and `requirements.md` updates in the same commit as the related behavior change.
- Confirm no static shared entry password is committed; the gate password is initialized in the database on first run.
