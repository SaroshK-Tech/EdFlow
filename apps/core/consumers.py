"""WebSocket consumer for live school-wide updates (Channels, spec §29).

Clients connect to ``/ws/school/`` and automatically join:

* the global ``school_live`` group → school-wide events (attendance saves,
  communication queue progress),
* their personal ``user_{pk}`` group → private notifications for that user.

Auth uses the standard Django session (AuthMiddlewareStack), so a logged-in
session can open the socket directly from the dashboard.
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.core.realtime import SCHOOL_GROUP

logger = logging.getLogger(__name__)


class SchoolEventConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.groups = [SCHOOL_GROUP]
        user = self.scope.get("user")
        if user is not None and user.is_authenticated:
            self.groups.append(f"user_{user.pk}")
        for group in self.groups:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()
        await self.send_json(
            {"type": "connected", "payload": {"groups": self.groups}}
        )

    async def disconnect(self, code):
        for group in self.groups:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def school_event(self, event):
        await self.send_json(
            {"type": event.get("event", "update"), "payload": event.get("payload", {})}
        )