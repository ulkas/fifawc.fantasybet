param(
    [ValidateSet("preflight", "remote-preflight", "backup", "deploy", "postcheck", "sync-artifacts")]
    [string]$Action = "preflight"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DeployHost = if ($env:DEPLOY_HOST) { $env:DEPLOY_HOST } else { "" }
$DeploySshKey = if ($env:DEPLOY_SSH_KEY) { $env:DEPLOY_SSH_KEY } else { "" }
$DeployKnownHostsFile = if ($env:DEPLOY_KNOWN_HOSTS_FILE) { $env:DEPLOY_KNOWN_HOSTS_FILE } else { "" }
$DeployKnownHosts = if ($env:DEPLOY_KNOWN_HOSTS) { $env:DEPLOY_KNOWN_HOSTS } else { "" }
$DeployAppDir = if ($env:DEPLOY_APP_DIR) { $env:DEPLOY_APP_DIR } else { "/opt/wcf" }
$DeployPublicUrl = if ($env:DEPLOY_PUBLIC_URL) { $env:DEPLOY_PUBLIC_URL } else { "https://ulkas.duckdns.org/fantasy/" }
$DeployPublicBaseUrl = if ($env:DEPLOY_PUBLIC_BASE_URL) { $env:DEPLOY_PUBLIC_BASE_URL.TrimEnd("/") } else { $DeployPublicUrl.TrimEnd("/") }
$DeployMinFreeMb = if ($env:DEPLOY_MIN_FREE_MB) { [int]$env:DEPLOY_MIN_FREE_MB } else { 1024 }
$DeployMode = if ($env:DEPLOY_MODE) { $env:DEPLOY_MODE } else { "archive-copy" }
$AllowDirty = ($env:ALLOW_DIRTY -eq "1")
$BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { "/opt/wcf/backups" }
$DeployBranch = if ($env:DEPLOY_BRANCH) { $env:DEPLOY_BRANCH } else { "" }
$script:DeployKnownHostsTempFile = ""

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Invoke-QuietChecked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    $null = & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Invoke-DockerCompose {
    param(
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        & docker-compose @Arguments
    } else {
        & docker compose @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Invoke-DockerComposeQuiet {
    param(
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        $null = & docker-compose @Arguments *> $null
    } else {
        $null = & docker compose @Arguments *> $null
    }
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-GitValue {
    param([string[]]$Arguments)
    $value = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Arguments -join ' ')"
    }
    return ($value | Select-Object -First 1)
}

function Get-SshBaseArgs {
    if (-not $DeployHost) {
        throw "DEPLOY_HOST is required for remote deployment actions."
    }
    if (-not $DeploySshKey) {
        throw "DEPLOY_SSH_KEY is required for remote deployment actions."
    }
    if (-not (Test-Path $DeploySshKey)) {
        throw "SSH key not found at $DeploySshKey"
    }

    $args = @(
        "-i", $DeploySshKey,
        "-o", "IdentitiesOnly=yes",
        "-o", "BatchMode=yes"
    )

    if ($DeployKnownHostsFile) {
        if (-not (Test-Path $DeployKnownHostsFile)) {
            throw "Known hosts file not found at $DeployKnownHostsFile"
        }
        return $args + @(
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=$DeployKnownHostsFile"
        )
    }

    if ($DeployKnownHosts) {
        if (-not $script:DeployKnownHostsTempFile) {
            $script:DeployKnownHostsTempFile = Join-Path ([System.IO.Path]::GetTempPath()) "wcf-known-hosts-$([System.Guid]::NewGuid().ToString('N'))"
            [System.IO.File]::WriteAllText($script:DeployKnownHostsTempFile, $DeployKnownHosts.Trim() + [Environment]::NewLine)
        }
        return $args + @(
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=$script:DeployKnownHostsTempFile"
        )
    }

    return $args + @("-o", "StrictHostKeyChecking=accept-new")
}

function New-WorkspaceArchive {
    param(
        [string]$ArchivePath
    )

    $fileListPath = Join-Path ([System.IO.Path]::GetTempPath()) "wcf-files-$([System.Guid]::NewGuid().ToString('N')).txt"
    try {
        $trackedAndUntracked = & git ls-files --cached --others --exclude-standard
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to list deployable workspace files."
        }

        $existingFiles = @(
            $trackedAndUntracked |
                Where-Object {
                    $_ -and (Test-Path -LiteralPath (Join-Path $Workspace $_) -PathType Leaf)
                }
        )
        if (-not $existingFiles) {
            throw "No deployable workspace files were found."
        }

        [System.IO.File]::WriteAllLines($fileListPath, [string[]]$existingFiles)
        Invoke-Checked "tar" @("-cf", $ArchivePath, "-T", $fileListPath) "Failed to create workspace deployment archive."
    }
    finally {
        if (Test-Path $fileListPath) {
            Remove-Item -LiteralPath $fileListPath -Force
        }
    }
}

function Test-LocalPreflight {
    Push-Location $Workspace
    try {
        Write-Step "Local preflight"
        if ($DeployMode -notin @("archive-copy", "git-pull")) {
            throw "Unsupported DEPLOY_MODE '$DeployMode'. Supported values: archive-copy, git-pull."
        }

        $branch = Get-GitValue @("rev-parse", "--abbrev-ref", "HEAD")
        $revision = Get-GitValue @("rev-parse", "HEAD")
        if (-not $script:DeployBranch) {
            $script:DeployBranch = $branch
        }

        $dirty = & git status --porcelain
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect local Git status."
        }
        if ($dirty -and $DeployMode -eq "git-pull" -and -not $AllowDirty) {
            throw "Local worktree is dirty. Commit or stash changes before production deploy, or set ALLOW_DIRTY=1 only for non-production validation."
        }

        Write-Host "Branch: $branch"
        Write-Host "Revision: $revision"
        Write-Host "Deploy mode: $DeployMode"
        if ($DeployMode -eq "archive-copy") {
            Write-Host "Deploy source: current workspace files"
        }
        Write-Host "Target: $DeployHost`:$DeployAppDir"
        Write-Host "Dirty worktree: $(if ($dirty) { 'yes' } else { 'no' })"

        Invoke-DockerComposeQuiet @("config") "Docker Compose config failed."
        if (Test-Path (Join-Path $Workspace ".env.production")) {
            Invoke-DockerComposeQuiet @("-f", "docker-compose.prod.yml", "config") "Production compose config failed."
        } else {
            Write-Host "Production compose config skipped locally because .env.production is absent; remote preflight validates it on the VPS."
        }

    }
    finally {
        Pop-Location
    }
}

function Invoke-RemoteScript {
    param(
        [string]$Script,
        [string[]]$RemoteArgs = @()
    )
    $sshArgs = (Get-SshBaseArgs) + @(
        $DeployHost,
        "bash", "-s", "--"
    ) + $RemoteArgs
    $Script | & ssh @sshArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed over SSH."
    }
}

function Update-RemotePublicBaseUrl {
    Write-Step "Remote PUBLIC_BASE_URL sync"
    $script = @'
set -eu
APP_DIR="$1"
TARGET_BASE_URL="$2"
TARGET_HOST="$3"
cd "$APP_DIR"

if [ ! -f .env.production ]; then
  echo "Missing .env.production"
  exit 1
fi

tmp_file="$(mktemp)"
awk -v base_url="$TARGET_BASE_URL" -v host="$TARGET_HOST" '
  BEGIN { base_seen = 0; host_seen = 0; allowed_seen = 0; csrf_seen = 0 }
  /^PUBLIC_BASE_URL=/ {
    print "PUBLIC_BASE_URL=" base_url
    base_seen = 1
    next
  }
  /^SERVER_NAME=/ {
    print "SERVER_NAME=" host
    host_seen = 1
    next
  }
  /^DJANGO_ALLOWED_HOSTS=/ {
    print "DJANGO_ALLOWED_HOSTS=" host
    allowed_seen = 1
    next
  }
  /^DJANGO_CSRF_TRUSTED_ORIGINS=/ {
    print "DJANGO_CSRF_TRUSTED_ORIGINS=https://" host
    csrf_seen = 1
    next
  }
  { print }
  END {
    if (!base_seen) print "PUBLIC_BASE_URL=" base_url
    if (!host_seen) print "SERVER_NAME=" host
    if (!allowed_seen) print "DJANGO_ALLOWED_HOSTS=" host
    if (!csrf_seen) print "DJANGO_CSRF_TRUSTED_ORIGINS=https://" host
  }
' .env.production > "$tmp_file"
cat "$tmp_file" > .env.production
rm -f "$tmp_file"
echo "Public URL and host settings updated to deploy target."
'@
    $deployHostName = ([uri]$DeployPublicUrl).Host
    Invoke-RemoteScript $script @($DeployAppDir, $DeployPublicBaseUrl, $deployHostName)
}

function Test-RemotePreflight {
    Write-Step "Remote preflight"
    $script = @'
set -eu
APP_DIR="$1"
MIN_FREE_MB="$2"
DEPLOY_MODE="$3"
DEPLOY_BRANCH="${4:-}"
if [ ! -d "$APP_DIR" ]; then
  if [ "$DEPLOY_MODE" = "archive-copy" ]; then
    mkdir -p "$APP_DIR"
    chmod 700 "$APP_DIR"
    echo "Created missing app dir for archive-copy bootstrap: $APP_DIR"
  else
    echo "Missing app dir: $APP_DIR"
    exit 1
  fi
fi
cd "$APP_DIR"

required_env_keys="DJANGO_SECRET_KEY DJANGO_DEBUG DJANGO_ALLOWED_HOSTS DJANGO_CSRF_TRUSTED_ORIGINS PUBLIC_BASE_URL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT"

echo "Remote host: $(hostname)"
echo "App dir: $APP_DIR"

free_mb="$(df -Pm "$APP_DIR" | awk 'NR==2 {print $4}')"
if [ "$free_mb" -lt "$MIN_FREE_MB" ]; then
  echo "Insufficient free disk: ${free_mb}MB available, need ${MIN_FREE_MB}MB"
  exit 1
fi
echo "Disk free: ${free_mb}MB"

mem_mb="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
echo "Memory available: ${mem_mb}MB"

docker version >/dev/null
docker compose version >/dev/null
if [ -f docker-compose.prod.yml ]; then
  docker compose -f docker-compose.prod.yml config >/dev/null
else
  if [ "$DEPLOY_MODE" = "archive-copy" ]; then
    echo "Production compose file missing; initial archive deploy will provide it."
  else
    echo "Missing docker-compose.prod.yml"
    exit 1
  fi
fi

if [ ! -f .env.production ]; then
  echo "Missing .env.production"
  exit 1
fi

env_perm="$(stat -c %a .env.production 2>/dev/null || echo unknown)"
case "$env_perm" in
  600|640|660) echo "Env permissions: $env_perm" ;;
  *) echo "Warning: .env.production permissions are $env_perm; prefer 600 or 640." ;;
esac

for key in $required_env_keys; do
  if ! grep -Eq "^${key}=" .env.production; then
    echo "Missing required env key: $key"
    exit 1
  fi
done

if grep -Eiq 'replace-with|changeme|unsafe-dev-secret-key' .env.production; then
  echo "Env file appears to contain placeholder secret values."
  exit 1
fi
if grep -Eq '^(DJANGO_ALLOWED_HOSTS|DJANGO_CSRF_TRUSTED_ORIGINS|PUBLIC_BASE_URL|SERVER_NAME)=.*example\.com' .env.production; then
  echo "Env file appears to contain placeholder values."
  exit 1
fi

if grep -Eq '^DJANGO_DEBUG=(1|true|True|yes|on)$' .env.production; then
  echo "Production debug mode is enabled."
  exit 1
fi

if [ "$DEPLOY_MODE" = "git-pull" ]; then
  git rev-parse --is-inside-work-tree >/dev/null
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ -n "$DEPLOY_BRANCH" ] && [ "$current_branch" != "$DEPLOY_BRANCH" ]; then
    echo "Remote branch is $current_branch, expected $DEPLOY_BRANCH"
    exit 1
  fi
  if [ -n "$(git status --porcelain)" ]; then
    echo "Remote worktree is dirty."
    exit 1
  fi
  echo "Remote branch: $current_branch"
  echo "Remote revision: $(git rev-parse HEAD)"
else
  echo "Deploy mode: archive-copy"
  if [ -f .deploy-revision ]; then
    echo "Current deployed revision: $(cat .deploy-revision)"
  else
    echo "Current deployed revision: unknown"
  fi
fi

if ! docker network inspect edge >/dev/null 2>&1; then
  echo "Missing shared Docker network: edge"
  exit 1
fi

if [ -f docker-compose.prod.yml ]; then
  docker compose -f docker-compose.prod.yml ps
fi
[ -f /opt/reverse-proxy/docker-compose.yml ] && docker compose -f /opt/reverse-proxy/docker-compose.yml ps || echo "Warning: /opt/reverse-proxy/docker-compose.yml not found; cannot inspect shared proxy compose stack."
'@
    Invoke-RemoteScript $script @($DeployAppDir, "$DeployMinFreeMb", $DeployMode, $DeployBranch)
}

function Invoke-RemoteBackup {
    Write-Step "Remote backup"
    $script = @'
set -eu
APP_DIR="$1"
BACKUP_ROOT="$2"
cd "$APP_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="${BACKUP_ROOT%/}/deploy-$stamp"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

if [ -f docker-compose.prod.yml ]; then
  docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup_dir/database.sql"
else
  echo "No existing compose stack; initial deploy has no database backup." > "$backup_dir/database-backup.txt"
fi
if [ -f docker-compose.prod.yml ] && docker compose -f docker-compose.prod.yml exec -T web test -d /app/media; then
  docker compose -f docker-compose.prod.yml exec -T web tar -czf - -C /app/media . > "$backup_dir/media.tar.gz"
else
  echo "No /app/media directory found; skipping media backup." > "$backup_dir/media-backup.txt"
fi
cp .env.production "$backup_dir/env.production"
if [ -f docker-compose.prod.yml ]; then
  cp docker-compose.prod.yml "$backup_dir/docker-compose.prod.yml"
fi
if [ -d nginx ]; then
  tar -czf "$backup_dir/nginx-config.tar.gz" nginx
fi
chmod 600 "$backup_dir"/* 2>/dev/null || true
echo "Backup path: $backup_dir"
'@
    Invoke-RemoteScript $script @($DeployAppDir, $BackupDir)
}

function Invoke-RemoteDeploy {
    Write-Step "Remote deploy"
    $script = @'
set -eu
APP_DIR="$1"
DEPLOY_BRANCH="$2"
cd "$APP_DIR"

before="$(git rev-parse HEAD)"
branch="$(git rev-parse --abbrev-ref HEAD)"
if [ -n "$DEPLOY_BRANCH" ] && [ "$branch" != "$DEPLOY_BRANCH" ]; then
  echo "Remote branch is $branch, expected $DEPLOY_BRANCH"
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Remote worktree is dirty."
  exit 1
fi

git fetch origin "$branch"
git pull --ff-only origin "$branch"
after="$(git rev-parse HEAD)"
echo "Revision before: $before"
echo "Revision after: $after"

docker compose -f docker-compose.prod.yml up -d --build
'@
    Invoke-RemoteScript $script @($DeployAppDir, $DeployBranch)
}

function Invoke-ArchiveDeploy {
    Push-Location $Workspace
    try {
        Write-Step "Archive deploy"
        $revision = Get-GitValue -Arguments @("rev-parse", "HEAD")
        $shortRevision = Get-GitValue -Arguments @("rev-parse", "--short", "HEAD")
        $dirty = & git status --porcelain
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect local Git status."
        }
        $deployRevision = if ($dirty) {
            "$revision+worktree.$(Get-Date -Format 'yyyyMMddHHmmss')"
        } else {
            $revision
        }
        $archivePath = Join-Path ([System.IO.Path]::GetTempPath()) "wcf-$shortRevision.tar"
        $remoteArchive = "/tmp/wcf-$shortRevision.tar"

        if (Test-Path $archivePath) {
            Remove-Item -LiteralPath $archivePath -Force
        }
        New-WorkspaceArchive -ArchivePath $archivePath
        try {
            Invoke-Checked "scp" ((Get-SshBaseArgs) + @($archivePath, "${DeployHost}:$remoteArchive")) "Failed to upload deployment archive."
        }
        finally {
            if (Test-Path $archivePath) {
                Remove-Item -LiteralPath $archivePath -Force
            }
        }

        $script = @'
set -eu
APP_DIR="$1"
REMOTE_ARCHIVE="$2"
REVISION="$3"
cd "$APP_DIR"
if [ ! -f "$REMOTE_ARCHIVE" ]; then
  echo "Missing uploaded archive: $REMOTE_ARCHIVE"
  exit 1
fi
tar -xf "$REMOTE_ARCHIVE" -C "$APP_DIR"
printf '%s\n' "$REVISION" > "$APP_DIR/.deploy-revision"
rm -f "$REMOTE_ARCHIVE"
docker compose -f docker-compose.prod.yml up -d --build
echo "Revision deployed: $REVISION"
'@
        Invoke-RemoteScript $script @($DeployAppDir, $remoteArchive, $deployRevision)
    }
    finally {
        Pop-Location
    }
}

function Test-RemotePostcheck {
    Write-Step "Remote postcheck"
    $script = @'
set -eu
APP_DIR="$1"
PUBLIC_URL="$2"
cd "$APP_DIR"

docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec -T web python manage.py check < /dev/null
docker compose -f docker-compose.prod.yml exec -T web python manage.py import_schedule < /dev/null
docker compose -f docker-compose.prod.yml exec -T web python manage.py sync_scores < /dev/null

status=""
for attempt in $(seq 1 12); do
  status="$(curl -k -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL" || true)"
  case "$status" in
    200|301|302|403)
      echo "Public URL status: $status"
      break
      ;;
  esac
  echo "Public URL status attempt ${attempt}/12: $status"
  sleep 5
done

case "$status" in
  200|301|302|403) ;;
  *) echo "Unexpected public URL status after retries: $status"; exit 1 ;;
esac

echo "Recent warning/error log lines, if any:"
docker compose -f docker-compose.prod.yml logs --tail=120 web nginx 2>&1 | grep -Ei '\b(error|critical|traceback|exception)\b' | tail -20 || true

echo "Published ports for this stack:"
docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null | grep -E '"Publishers":\[\]' >/dev/null && echo "No host ports published by app containers." || docker compose -f docker-compose.prod.yml ps
'@
    Invoke-RemoteScript $script @($DeployAppDir, $DeployPublicUrl)
}

switch ($Action) {
    "preflight" {
        Test-LocalPreflight
    }
    "remote-preflight" {
        Test-RemotePreflight
    }
    "backup" {
        Test-RemotePreflight
        Invoke-RemoteBackup
    }
    "deploy" {
        Test-LocalPreflight
        Test-RemotePreflight
        Invoke-RemoteBackup
        Update-RemotePublicBaseUrl
        if ($DeployMode -eq "git-pull") {
            Invoke-RemoteDeploy
        } else {
            Invoke-ArchiveDeploy
        }
        Test-RemotePostcheck
    }
    "postcheck" {
        Test-RemotePostcheck
    }
    "sync-artifacts" {
        Test-LocalPreflight
        if ($DeployMode -ne "archive-copy") {
            throw "sync-artifacts is only available with DEPLOY_MODE=archive-copy."
        }
        Invoke-ArchiveDeploy
    }
}
