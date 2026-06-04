# Deployment Agent Runbook

This runbook defines the durable deployment process used by `.agents/deployment-agent.md` and `scripts/deploy.ps1`.

Deploy requests must route through `.agents/deployment-agent.md`; do not bypass the subagent and run deploy steps ad hoc from another instruction path.

## Hosting Shape

FIFA WC Fantasy Portal is a Django app deployed to a single Websupport VPS.

- Workstation: Windows workspace at `C:\develop\code\python\wcf`
- Production host: configured through `DEPLOY_HOST` in ignored local env or GitHub Environment secrets
- SSH key: configured through `DEPLOY_SSH_KEY` in ignored local env or `DEPLOY_SSH_PRIVATE_KEY` in GitHub Environment secrets
- App directory: `/opt/wcf`
- Public route: `https://ulkas.duckdns.org/fantasy/`
- Shared reverse proxy: Traefik in `/opt/reverse-proxy`
- App stack: Docker Compose in `/opt/wcf/docker-compose.prod.yml`
- App containers: `db`, `web`, `nginx`
- Persistent state: Postgres Docker volume, media Docker volume, static Docker volume, Gunicorn socket volume
- Shared Docker network: `edge`

The app is routed by Traefik with `Host(ulkas.duckdns.org) && PathPrefix(/fantasy)` on the `websecure` entrypoint, with matching HTTP traffic redirected to HTTPS, then forwarded to the app's internal Nginx container. Django generates prefixed URLs through `DJANGO_FORCE_SCRIPT_NAME=/fantasy`.

## Deploy Method

Default deployment is `DEPLOY_MODE=archive-copy`.

The production `/opt/wcf` directory is currently a copied app directory, not a Git worktree. The deployment script creates an archive from the current deployable workspace files, uploads that archive to the VPS, extracts it into `/opt/wcf`, records `.deploy-revision`, and rebuilds the app stack.

Archive-copy deploys include tracked files plus untracked files that are not ignored by Git. This makes normal `deploy` suitable for small local edits without committing first. Ignored/private material remains excluded, including env files, `.git-auth/`, logs, media, backups, caches, and generated static files.

```powershell
git push origin main
```

Production deploys run through GitHub Actions on pushes to `main`. Use the manual `Deploy FIFA WC Fantasy Portal` workflow only for `remote-preflight` or an explicit rerun. Use `.\scripts\deploy.ps1 deploy` only as the local fallback driver when GitHub automation is unavailable or the user explicitly asks for the local driver.

On the VPS this effectively performs:

```bash
tar -xf /tmp/wcf-<revision>.tar -C /opt/wcf
printf '<revision>\n' > /opt/wcf/.deploy-revision
docker compose -f docker-compose.prod.yml up -d --build
```

The `web` container entrypoint runs migrations and `collectstatic` before starting Gunicorn.

If `/opt/wcf` is later converted into a Git worktree with server-side Git auth, `DEPLOY_MODE=git-pull` is available. In that mode the remote worktree must be clean and the script uses `git pull --ff-only`.

## Direct Deploy Intent

A direct request such as "deploy", "redeploy", "push live", "update production", or "rollout" is approval to run the default deployment flow immediately. Do not ask for a second confirmation just because the flow will create a backup, upload an archive, rebuild/recreate this app stack, or smoke-check the public route.

Stop and report only when a safety blocker exists:

- ambiguous intended revision
- failed local or remote preflight
- failed backup
- failed tests/checks when tests are enabled
- risk of printing, uploading, committing, or exposing secrets/private data
- requested action outside the FIFA WC Fantasy Portal app stack or outside this runbook

In `archive-copy` mode, being ahead of `origin` or having a dirty local worktree is not itself a deploy blocker. The deploy artifact is created from current deployable workspace files based on local `HEAD`, so a direct deploy request should deploy those files unless the user explicitly says to deploy only remote state.

## Commit-And-Deploy Parallelism

For commit-and-deploy requests, the deployment subagent may start in parallel with the commit subagent. It does not need to wait for the commit before doing revision-independent work.

Safe parallel work includes:

- local and remote preflight checks
- target readiness checks
- production backup creation
- deploy parameter validation
- reporting blockers that would prevent deployment

The final artifact/deploy step is still source-bound. Immediately before creating the archive or running the deploy step, re-check the current branch, `HEAD`, and dirty status. In `archive-copy` mode, deploy current deployable workspace files and record a worktree marker when uncommitted changes are included. In `git-pull` mode, deploy only the intended clean committed revision.

## Configuration Variables

Set these as environment variables in PowerShell to customize the run:

- `DEPLOY_HOST`, required for remote actions
- `DEPLOY_SSH_KEY`, required for local fallback remote actions
- `DEPLOY_APP_DIR`, default `/opt/wcf`
- `DEPLOY_PUBLIC_URL`, default `https://ulkas.duckdns.org/fantasy/`
- `DEPLOY_PUBLIC_BASE_URL`, default `DEPLOY_PUBLIC_URL` without a trailing slash; during deploy this syncs only the non-secret `PUBLIC_BASE_URL` line in remote `.env.production` after backup
- `DEPLOY_MIN_FREE_MB`, default `1024`
- `DEPLOY_MODE`, default `archive-copy`
- `ALLOW_DIRTY`, default `0`
- `RUN_LOCAL_TESTS`, default `1`
- `BACKUP_DIR`, default `/opt/wcf/backups`
- `DEPLOY_BRANCH`, default current local branch
- `DEPLOY_KNOWN_HOSTS_FILE`, optional pinned known-hosts file for strict SSH host verification
- `DEPLOY_KNOWN_HOSTS`, optional pinned known-hosts content; used when no file path is supplied

Example:

```powershell
$env:DEPLOY_PUBLIC_URL = "https://ulkas.duckdns.org/fantasy/"
.\scripts\deploy.ps1 remote-preflight
```

## GitHub Actions Deployment

The workflow `.github/workflows/deploy.yml` targets the GitHub Environment `production` and runs automatically on pushes to `main`. Manual dispatch remains available for `remote-preflight` and `deploy`.

Required Environment secrets:

- `DEPLOY_HOST`: SSH login target for the production host
- `DEPLOY_SSH_PRIVATE_KEY`: private key authorized for the production host
- `DEPLOY_KNOWN_HOSTS`: pinned SSH host key line for the production host

Populate `DEPLOY_KNOWN_HOSTS` from an already trusted local `known_hosts` entry or a provider console fingerprint check. Do not generate it inside the deployment job with `ssh-keyscan`, because that would reintroduce trust-on-first-use during production deploy.

Optional Environment secrets override script defaults:

- `DEPLOY_APP_DIR`
- `DEPLOY_PUBLIC_URL`
- `DEPLOY_PUBLIC_BASE_URL`
- `DEPLOY_MIN_FREE_MB`

Workflow inputs:

- `remote-preflight`: local CI checks plus remote preflight only
- `deploy`: local CI checks, remote preflight, backup, remote `PUBLIC_BASE_URL` sync, archive deploy, and postcheck with public URL retries after container recreation

The workflow writes SSH material only to `$RUNNER_TEMP`, uses strict host-key checking through `DEPLOY_KNOWN_HOSTS`, and does not print private keys or raw `.env.production` content.

## Preflight

Local preflight verifies:

- current branch and revision
- dirty worktree status for reporting
- deploy mode
- Docker Compose file validity
- Django test suite, unless `RUN_LOCAL_TESTS=0`

Local tests run inside Docker:

```powershell
docker-compose run --rm --no-deps -e DJANGO_USE_SQLITE=1 -e POSTGRES_HOST= web python manage.py test
```

Remote preflight verifies:

- SSH connectivity
- disk free space and memory availability
- Docker and Docker Compose availability
- `/opt/wcf` exists, or creates it for first-run `archive-copy` bootstrap
- Git state only when `DEPLOY_MODE=git-pull`
- `.env.production` exists and contains required keys
- obvious placeholder secrets are not present
- `DJANGO_DEBUG` is disabled
- shared Docker network `edge` exists
- app compose can be inspected when already present; first-run `archive-copy` deploy may provide it

The script validates `.env.production` by key presence, permissions, placeholder detection, and known-safe settings only. It must not print raw env values.

## Backup

Before deploy, the script creates a private timestamped backup:

```text
/opt/wcf/backups/deploy-YYYYMMDD-HHMMSS/
```

The backup contains:

- `database.sql` from the Postgres container when an existing compose stack is present, otherwise a first-deploy note
- `media.tar.gz` from `/app/media` when that directory exists, otherwise a note that no media directory was present
- private `.env.production` snapshot
- `docker-compose.prod.yml`
- Nginx config archive when present

Backup files are private production data. Do not copy, print, or commit them.

Backup may run before a parallel commit finishes because it captures the current production state, not local source state. If deploy is later cancelled, report the backup path and that no source change was applied.

## Deploy

The deploy step updates only `/opt/wcf` from the current deployable workspace archive and starts only this app stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

It does not restart unrelated applications, remove volumes, prune Docker objects, change Traefik routes outside this app, or rotate secrets.

After backup and before archive extraction, the script may update the canonical public routing settings in `/opt/wcf/.env.production` to match `DEPLOY_PUBLIC_URL`:

- `PUBLIC_BASE_URL`
- `SERVER_NAME`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`

This keeps generated public image links and the host-facing nginx/Django settings aligned without exposing or rewriting secret values.

When a deployment subagent started before a commit completed, rerun the local revision/dirty checks immediately before this step so the uploaded archive matches the final intended source.

## Postcheck

Postcheck verifies:

- app compose service status
- `docker compose -f docker-compose.prod.yml exec -T web python manage.py check`
- public URL returns `200`, `301`, `302`, or `403`
- recent app logs do not show obvious new errors
- stack port exposure remains limited to the intended Traefik routing model

For the current private app, an unauthenticated public URL redirect to login is healthy.

## Rollback

Use the backup path from the deploy report. The safest first rollback for a bad code deploy is a Git revert or a redeploy of the previous known-good commit, followed by:

```bash
docker compose -f /opt/wcf/docker-compose.prod.yml up -d --build
```

Database/media rollback is more destructive and should be explicit. If needed, restore from the deploy backup only after confirming the impact on newer user data.

Manual restore shape:

```bash
cd /opt/wcf
cat /opt/wcf/backups/deploy-YYYYMMDD-HHMMSS/database.sql | docker compose -f docker-compose.prod.yml exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
test -f /opt/wcf/backups/deploy-YYYYMMDD-HHMMSS/media.tar.gz && docker compose -f docker-compose.prod.yml exec -T web tar -xzf - -C /app/media < /opt/wcf/backups/deploy-YYYYMMDD-HHMMSS/media.tar.gz
docker compose -f docker-compose.prod.yml up -d --build
```

Do not run destructive cleanup commands during rollback unless explicitly requested and confirmed.

## Customizing For Another Host

To deploy the same project elsewhere:

1. Create the app directory on the host.
2. Install Docker Engine and Docker Compose plugin.
3. Create the shared `edge` network or adjust the compose labels/network.
4. Put a production `.env.production` in the app directory.
5. Set `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, `DEPLOY_APP_DIR`, and `DEPLOY_PUBLIC_URL` if you are using the local fallback driver.
6. Update `APP_PUBLIC_HOST`, `APP_PATH_PREFIX`, `PUBLIC_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, cookie paths, and `DJANGO_FORCE_SCRIPT_NAME` for the new domain/path.
7. Run `.\scripts\deploy.ps1 remote-preflight`.

## Speed Notes

- Use `RUN_LOCAL_TESTS=0` only when the exact clean revision was verified recently.
- Docker rebuilds are usually the slowest step.
- The app entrypoint always runs migrations and `collectstatic`; expect startup to take longer after dependency/static changes.
- Remote preflight and production backup can run before committing or pushing; artifact creation and deploy must re-check and use the final intended source.

## Known Gotchas

- DuckDNS is server-wide DNS only; keep app isolation on path prefixes such as `/fantasy` and `/gg100`.
- Dirty local worktrees are allowed in `archive-copy` mode because the production flow deploys current workspace files while excluding ignored/private material.
- Archive deployment overwrites tracked files but does not delete old untracked files from previous releases; if a stale tracked file must be removed from production, plan and review that cleanup explicitly.
- Remote local edits in `/opt/wcf` can be overwritten when they touch tracked paths. Keep production-only data in `.env.production`, Docker volumes, or backup directories, not tracked source paths.
- Git pushes for this repo should use the repo-local `ulkas` GitHub identity; do not change global Git auth.
- Never use the local `lukas-trojcak-tfs` GitHub identity or any corporate GitHub auth for this project.
- Never inspect or paste `.env.production`, `.git-auth/`, database dumps, media archives, private logs, or admin credentials into chat.
