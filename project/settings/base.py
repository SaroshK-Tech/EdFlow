"""Shared settings for EdFlow. Imported by dev/prod settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root (contains manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load local environment overrides (see .env.example, never committed).
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=None):
    raw = os.getenv(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Core ---
# A default is provided for convenience, but production MUST set a real value.
SECRET_KEY = os.getenv(
    "SECRET_KEY", "django-insecure-edflow-change-me"
)
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["*"])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

# --- Applications ---
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.school",
    "apps.students",
    "apps.parents",
    "apps.admissions",
    "apps.academics",
    "apps.timetable",
    "apps.attendance",
    "apps.staff",
    "apps.hr",
    "apps.payroll",
    "apps.houses",
    "apps.exams",
    "apps.results",
    "apps.progress",
    "apps.fees",
    "apps.finance",
    "apps.transport",
    "apps.library",
    "apps.inventory",
    "apps.discipline",
    "apps.communication",
    "apps.documents",
    "apps.reports",
    "apps.notifications",
    "apps.backup",
    "apps.hardware",
]

INSTALLED_APPS = (
    ["daphne"] + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"
ASGI_APPLICATION = "project.asgi.application"

# --- Database ---
# Defaults to SQLite (small dev/prototype). Production uses PostgreSQL: set
# DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD (or leave unset for SQLite).
_DB_HOST = os.getenv("DB_HOST")
if _DB_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": _DB_HOST,
            "PORT": os.getenv("DB_PORT", "5432"),
            "NAME": os.getenv("DB_NAME", "edflow"),
            "USER": os.getenv("DB_USER", "edflow"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "CONN_MAX_AGE": 600,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Auth ---
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- Internationalization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --- Static & media ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Runtime directories (created automatically; backups/logs are gitignored) ---
BACKUP_DIR = BASE_DIR / "backups"
LOGS_DIR = BASE_DIR / "logs"

for _runtime_dir in (MEDIA_ROOT, LOGS_DIR, BACKUP_DIR):
    _runtime_dir.mkdir(parents=True, exist_ok=True)

# --- Email (optional add-on; configure SMTP in .env, console in dev) ---
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "EdFlow <no-reply@school.local>"
)

# --- Admin location ---
ADMIN_URL = os.getenv("ADMIN_URL", "admin")

# --- Upload limits ---
# Reports/certificates/import files can be large; keep a reasonable cap.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(50 * 1024 * 1024))
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(50 * 1024 * 1024))
)

# --- Default primary key ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# --- CORS ---
CORS_ALLOW_ALL_ORIGINS = DEBUG

# --- Channels ---
# Redis-backed when REDIS_URL is set (production); in-memory layer otherwise
# so realtime features work fully offline on a small LAN (spec §29).
if os.getenv("REDIS_URL"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [os.getenv("REDIS_URL")],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# --- Celery ---
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_EXTENDED = True

# --- Communication gateway ---
# Shared secret the local Android Communication Gateway must present via the
# "X-Gateway-Token" header when pulling/reporting messages over LAN/USB.
# Empty by default: when empty, the gateway endpoints reject all requests.
COMMUNICATION_GATEWAY_TOKEN = os.getenv("COMMUNICATION_GATEWAY_TOKEN", "")

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": os.getenv("LOG_LEVEL", "INFO"),
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "edflow.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps.backup": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.communication": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}