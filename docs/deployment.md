# Deployment

The production stack mirrors the neighboring Django projects:

- PostgreSQL container for persistent data.
- Django/Gunicorn web container on a Unix socket.
- Nginx container serving static files and proxying to Gunicorn.
- Shared external Docker network `edge`.
- Shared Traefik reverse proxy routing `Host(ulkas.duckdns.org) && PathPrefix(/fantasy)`.

Local development follows the same container boundary: run Django, Python, tests, imports, sync jobs, and database access only through Docker Compose. Do not install project dependencies or execute project management commands on the host.

Expected VPS layout:

- App stack: `/opt/wcf`
- Shared reverse proxy: `/opt/reverse-proxy`
- Public URL: `https://ulkas.duckdns.org/fantasy/`
- Git remote: `git@github.com:ulkas/fifawc.fantasybet.git`

All Git-backed deployment work must use the personal GitHub user `ulkas`. Verify repo-local Git identity, remote, and SSH key before any Git operation. Never use the company user `lukas-trojcak-tfs` or corporate GitHub credentials.

Production deploys follow the same GitHub Actions/archive-copy model as the neighboring AWW project:

- Pushing `main` to `git@github.com:ulkas/fifawc.fantasybet.git` triggers `.github/workflows/deploy.yml`.
- The workflow uses the GitHub Environment `production`.
- Required environment secrets are `DEPLOY_HOST`, `DEPLOY_SSH_PRIVATE_KEY`, and `DEPLOY_KNOWN_HOSTS`.
- Optional environment secrets can override `DEPLOY_APP_DIR`, `DEPLOY_PUBLIC_URL`, `DEPLOY_PUBLIC_BASE_URL`, and `DEPLOY_MIN_FREE_MB`.
- The default deployment driver is `scripts/deploy.ps1` in `archive-copy` mode. It archives deployable workspace files, uploads them to `/opt/wcf`, records `.deploy-revision`, rebuilds only this app stack, and postchecks `https://ulkas.duckdns.org/fantasy/`.
- `scripts/deploy.ps1` must not contain concrete hostnames, IP addresses, or local private-key paths. Set `DEPLOY_HOST` and `DEPLOY_SSH_KEY` through ignored local environment variables for manual fallback deploys.

Use the manual workflow only for `remote-preflight` or an explicit rerun. Use `.\scripts\deploy.ps1 deploy` only as the local fallback when GitHub automation is unavailable or explicitly requested.

Required production path settings:

```env
PUBLIC_BASE_URL=https://ulkas.duckdns.org/fantasy
DJANGO_FORCE_SCRIPT_NAME=/fantasy
DJANGO_SESSION_COOKIE_NAME=fantasy_sessionid
DJANGO_SESSION_COOKIE_PATH=/fantasy
DJANGO_CSRF_COOKIE_NAME=fantasy_csrftoken
DJANGO_CSRF_COOKIE_PATH=/fantasy
APP_PUBLIC_HOST=ulkas.duckdns.org
APP_PATH_PREFIX=/fantasy
```

The shared portal entry password is intentionally not set through environment variables. On a fresh database, the first password submitted on the landing page is hashed and stored in the app database as the shared entry password.

Hourly score sync can be installed as VPS cron:

```bash
0 * * * * cd /opt/wcf && docker compose -f docker-compose.prod.yml exec -T web python manage.py sync_scores >> /var/log/wcf-sync.log 2>&1
```
