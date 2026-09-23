"""Demo settings: dedicated demo.sqlite3 database, DEBUG on.

Used to build and serve the marketing/product demo data safely without
touching the real development database (db.sqlite3).
"""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "demo.sqlite3",
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"