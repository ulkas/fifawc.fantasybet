from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    value = env(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    value = env(key, default) or ""
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-dev-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
FORCE_SCRIPT_NAME = (env("DJANGO_FORCE_SCRIPT_NAME", "") or "").rstrip("/") or None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "fantasy.apps.FantasyConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "fantasy.middleware.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "fantasy.context_processors.current_player",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"
ASGI_APPLICATION = "project.asgi.application"

if env_bool("DJANGO_USE_SQLITE", False) or not env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "fantasy"),
            "USER": env("POSTGRES_USER", "fantasy"),
            "PASSWORD": env("POSTGRES_PASSWORD", "fantasy"),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Europe/Warsaw")
USE_I18N = True
USE_TZ = True

STATIC_URL = f"{FORCE_SCRIPT_NAME or ''}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_NAME = env("DJANGO_SESSION_COOKIE_NAME", "fantasy_sessionid")
SESSION_COOKIE_PATH = env("DJANGO_SESSION_COOKIE_PATH", FORCE_SCRIPT_NAME or "/")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(env("DJANGO_SESSION_COOKIE_AGE", str(60 * 60 * 24 * 365 * 10)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_NAME = env("DJANGO_CSRF_COOKIE_NAME", "fantasy_csrftoken")
CSRF_COOKIE_PATH = env("DJANGO_CSRF_COOKIE_PATH", FORCE_SCRIPT_NAME or "/")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = int(env("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
if not env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", True):
    del SECURE_PROXY_SSL_HEADER

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'"
)

PUBLIC_BASE_URL = (env("PUBLIC_BASE_URL", "") or "").rstrip("/")
FANTASY_GATE_COOKIE = env("FANTASY_GATE_COOKIE", "fantasy_gate")
FANTASY_DEVICE_COOKIE = env("FANTASY_DEVICE_COOKIE", "fantasy_device")
FANTASY_COOKIE_AGE = int(env("FANTASY_COOKIE_AGE", str(60 * 60 * 24 * 365 * 10)))
FANTASY_OPENFOOTBALL_URL = env(
    "FANTASY_OPENFOOTBALL_URL",
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
)
FANTASY_FIFA_SCHEDULE_URL = env(
    "FANTASY_FIFA_SCHEDULE_URL",
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums",
)
FANTASY_FIFA_SCORES_URL = env(
    "FANTASY_FIFA_SCORES_URL",
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures",
)
