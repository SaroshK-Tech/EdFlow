"""Celery application for EdFlow (spec §29 background processing).

Background use-cases enabled here: asynchronous backup runs, scheduled
message promotion and broadcast notification dispatch. Runs without a broker
in dev; point REDIS_URL at a local Redis for production (see DEPLOYMENT.md).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.dev")

app = Celery("edflow")

# Load settings from Django (CELERY_* namespace in base.py).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover ``tasks.py`` in each installed app automatically.
app.autodiscover_tasks()