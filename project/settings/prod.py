"""Production settings for a school LAN server (spec §39).

PostgreSQL, DEBUG off, security headers appropriate for a trusted LAN
intranet (no forced HTTPS by default). All sensitive values come from
environment variables (see .env.example and documentation/DEPLOYMENT.md).

TLS is optional: set COOKIE_SECURE=true and ENABLE_HSTS=true only when the
school fronts EdFlow with a reverse proxy that terminates HTTPS.
"""

import sys

from .base import *  # noqa: F401,F403

DEBUG = False

# SECRET_KEY must be set explicitly in production (no fallback).
try:
    SECRET_KEY = os.environ["SECRET_KEY"]
except KeyError:
    sys.stderr.write(
        "\n[ERROR] SECRET_KEY is not set.\n"
        "Set SECRET_KEY in .env (see .env.example).\n\n"
    )
    raise

# --- Hosts ---
# Reject the debug wildcard in production; the school must pin its LAN
# addresses/hostnames (e.g. ALLOWED_HOSTS=localhost,192.168.1.10,edflow).
_allowed = env_list("ALLOWED_HOSTS", [])
if not _allowed or "*" in _allowed:
    sys.stderr.write(
        "\n[ERROR] ALLOWED_HOSTS must be pinned in production "
        "(comma-separated, no wildcards).\n"
        "Example: ALLOWED_HOSTS=localhost,192.168.1.10,edflow.local\n\n"
    )
    raise RuntimeError("ALLOWED_HOSTS not pinned")
ALLOWED_HOSTS = _allowed

# --- Database ---
# Requires DB_HOST etc. from the environment (PostgreSQL on the LAN server).
if not os.getenv("DB_HOST"):
    sys.stderr.write(
        "\n[ERROR] DB_HOST is not set. Production must use PostgreSQL.\n"
        "Set DB_HOST/DB_NAME/DB_USER/DB_PASSWORD in .env "
        "(see documentation/DEPLOYMENT.md).\n\n"
    )
    raise RuntimeError("DB_HOST not set")

# --- Security headers ---
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("COOKIE_SECURE", False)
SESSION_COOKIE_SECURE = env_bool("COOKIE_SECURE", False)
SECURE_SSL_REDIRECT = env_bool("ENABLE_HSTS", False)
SECURE_HSTS_SECONDS = 31536000 if env_bool("ENABLE_HSTS", False) else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("ENABLE_HSTS", False)
SECURE_HSTS_PRELOAD = env_bool("ENABLE_HSTS", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool(
    "ENABLE_HSTS", False
) else None

# --- Admin ---
# Move the Django admin off the default /admin/ path for reduced exposure.
ADMIN_URL = os.getenv("ADMIN_URL", "admin")