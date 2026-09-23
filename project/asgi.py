"""ASGI config for EdFlow (Django Channels). Exposes ``application`` (HTTP + WS)."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.dev")

from project.routing import application  # noqa: E402  (ProtocolTypeRouter)

__all__ = ("application",)