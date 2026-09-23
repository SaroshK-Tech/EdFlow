# This file is required by Django to load ``project.celery`` on startup.
from .celery import app as celery_app

__all__ = ("celery_app",)