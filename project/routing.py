"""ASGI routing: HTTP (Django) + WebSockets (Channels) for EdFlow.

``daphne project.asgi:application`` serves both from one process (LAN server).
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.dev")

django_asgi_app = get_asgi_application()

import apps.core.routing  # noqa: E402  (needs Django loaded)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(apps.core.routing.websocket_urlpatterns)
        ),
    }
)