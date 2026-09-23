"""WebSocket URL routes for live updates (Channels, spec §29)."""

from django.urls import re_path

from apps.core.consumers import SchoolEventConsumer

websocket_urlpatterns = [
    re_path(r"^ws/school/$", SchoolEventConsumer.as_asgi()),
]