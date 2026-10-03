"""Django settings for the VISCANE conversion."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ASSET_DIR = BASE_DIR


def load_env_file(path, override=False):
    if not path.is_file():
        return
    original_env_keys = set(os.environ.keys())
    try:
        with path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                value = value.strip()
                if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                if key in original_env_keys:
                    continue
                if override or key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


load_env_file(BASE_DIR / ".env.example", override=False)
load_env_file(BASE_DIR / ".env.local", override=True)
load_env_file(BASE_DIR / ".env", override=True)


def parse_database_url(database_url):
    if not database_url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }

    if database_url.startswith("sqlite:///"):
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": database_url.replace("sqlite:///", "", 1),
        }

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or "5432"),
        "CONN_MAX_AGE": 60,
    }


SECRET_KEY = os.getenv("VISCANE_SECRET_KEY", "change-this-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if host.strip()]
FARMER_ONLY = os.getenv("VISCANE_FARMER_ONLY", "false").lower() in {"1", "true", "yes", "on"}
if not DEBUG and (SECRET_KEY == "change-this-key" or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Production requires VISCANE_SECRET_KEY and explicit DJANGO_ALLOWED_HOSTS.")

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.mobile.FarmerPortalMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "viscane.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [PROJECT_ASSET_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "viscane.jinja2.environment",
        },
    },
]

WSGI_APPLICATION = "viscane.wsgi.application"
ASGI_APPLICATION = "viscane.asgi.application"

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URI")
    or os.getenv("DATABASE_FALLBACK_URL")
    or ""
)
DATABASES = {
    "default": parse_database_url(DATABASE_URL),
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
LANGUAGES = [("en", "English"), ("hil", "Hiligaynon")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [PROJECT_ASSET_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = PROJECT_ASSET_DIR / "media"
PRIVATE_UPLOAD_ROOT = Path(os.getenv("VISCANE_PRIVATE_UPLOAD_ROOT", str(BASE_DIR / ".private")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("DJANGO_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_HSTS_PRELOAD", "false").lower() == "true"
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if value.strip()]
# Enable only behind a proxy that strips and sets this header itself.
if os.getenv("DJANGO_TRUST_PROXY", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SCAN_MAX_IMAGE_BYTES = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
