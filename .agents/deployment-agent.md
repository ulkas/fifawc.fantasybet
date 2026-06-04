# FIFA WC Fantasy Deployment Agent

Use this agent guidance for deployment, redeploy, push-live, update-production, rollout, or production-readiness work.

## Target

Production target:

```text
https://ulkas.duckdns.org/fantasy
```

Expected VPS app directory:

```text
/opt/wcf
```

Canonical GitHub remote:

```text
git@github.com:ulkas/fifawc.fantasybet.git
```

Deploy host and SSH key values are sensitive. They must come from ignored local environment variables or GitHub Environment secrets, not committed scripts or docs.

## Routing Requirements

- Use shared DuckDNS host `ulkas.duckdns.org`.
- Use shared Traefik `edge` network.
- Route by path prefix `/fantasy`.
- Do not bind app containers directly to public host ports in production.
- Keep Django path settings aligned:

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

The shared portal entry password is not an environment variable. On a fresh database, the first submitted landing-page gate password initializes it and stores it as a server-side hash.

## Command Rules

- Default deployment path is `git push origin main`, which triggers `.github/workflows/deploy.yml`.
- Use the manual GitHub Actions workflow for `remote-preflight` or an explicit rerun.
- Use `.\scripts\deploy.ps1 deploy` only as the local fallback driver when GitHub automation is unavailable or explicitly requested.
- Before any Git-backed deployment operation, verify the active repo-local Git identity is `ulkas`, the remote is `git@github.com:ulkas/fifawc.fantasybet.git`, and the SSH command uses ignored `.git-auth/` key material without exposing the concrete private-key path.
- Never use `lukas-trojcak-tfs` or corporate GitHub credentials.
- Do not hardcode concrete server IPs, login targets, tokens, or private-key paths in scripts or docs.
- Run production commands inside containers.
- Do not run host Python or host Django commands.
- Use:

```bash
docker compose -f /opt/wcf/docker-compose.prod.yml exec -T web python manage.py check
docker compose -f /opt/wcf/docker-compose.prod.yml exec -T web python manage.py migrate
docker compose -f /opt/wcf/docker-compose.prod.yml exec -T web python manage.py import_schedule
docker compose -f /opt/wcf/docker-compose.prod.yml exec -T web python manage.py sync_scores
```

## GitHub Actions Deployment

The deployment workflow targets the GitHub Environment `production` and runs automatically on pushes to `main`.

Required Environment secrets:

- `DEPLOY_HOST`: SSH login target for the production host
- `DEPLOY_SSH_PRIVATE_KEY`: private key authorized for the production host
- `DEPLOY_KNOWN_HOSTS`: pinned SSH host key line for the production host

Optional Environment secrets:

- `DEPLOY_HOST`
- `DEPLOY_APP_DIR`
- `DEPLOY_PUBLIC_URL`
- `DEPLOY_PUBLIC_BASE_URL`
- `DEPLOY_MIN_FREE_MB`

Default deployment mode is `archive-copy`: the workflow archives the deployable workspace files, uploads them to `/opt/wcf`, records `.deploy-revision`, rebuilds only this app stack, and postchecks `https://ulkas.duckdns.org/fantasy/`.

## Score Sync

Hourly sync should be installed through VPS cron or a similarly lightweight scheduler:

```bash
0 * * * * cd /opt/wcf && docker compose -f docker-compose.prod.yml exec -T web python manage.py sync_scores >> /var/log/wcf-sync.log 2>&1
```

## Documentation Updates

Any deployment, routing, environment, sync scheduling, or operational change must update:

- `requirements.md`
- `README.md`
- `docs/deployment.md`
- other relevant `docs/` files

Do not finish deployment work with stale documentation.
