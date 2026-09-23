"""Development settings. SQLite, DEBUG on, local media served by Django."""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "db.sqlite3",
}

# Run Channels without Redis in development (still works with single process).
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"