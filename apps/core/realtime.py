"""Shared WebSocket + Celery helpers (spec §24/§29 real-time features).

``notify_user`` and ``broadcast`` push live updates to connected dashboards
(attendance saves, communication queue progress, new announcements…).
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

SCHOOL_GROUP = "school_live"


def notify_user(user, event, payload=None):
    """Deliver ``{type: event, payload: payload}`` to one user's sockets."""
    if not user or not user.is_authenticated:
        return
    _send(f"user_{user.pk}", event, payload)


def broadcast(event, payload=None):
    """Deliver an event to every connected dashboard socket (school-wide)."""
    _send(SCHOOL_GROUP, event, payload)


def _send(group, event, payload):
    try:
        layer = get_channel_layer()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("realtime unavailable: %s", exc)
        return
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            group,
            {
                "type": "school.event",
                "event": event,
                "payload": payload or {},
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("realtime group_send failed: %s", exc)