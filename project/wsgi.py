"""WSGI config for EdFlow. Exposes the WSGI callable as ``application``."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.dev")

application = get_wsgi_application()