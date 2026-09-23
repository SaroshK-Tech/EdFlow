"""Celery tasks for the communication queue (spec §12/§36)."""

import logging

from celery import shared_task

from apps.core.realtime import broadcast

logger = logging.getLogger(__name__)


@shared_task
def promote_scheduled_messages():
    """Mark due 'scheduled' outbox rows as pending so the gateway can claim them."""
    from django.utils import timezone

    from apps.communication.models import Outbox, OutboxStatus

    rows = Outbox.objects.filter(
        status=OutboxStatus.SCHEDULED, scheduled_at__lte=timezone.now()
    )
    count = rows.update(status=OutboxStatus.PENDING)
    if count:
        broadcast("queue.updated", {"promoted": count})
    return {"promoted": count}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def dispatch_ready_messages_task(self, limit=50):
    """Attempt delivery of pending messages (autosend), retrying on failure."""
    from apps.communication.services import autosend

    try:
        sent, failed = autosend(limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        raise self.retry(exc=exc)
    if sent or failed:
        broadcast("queue.updated", {"sent": sent, "failed": failed})
    return {"sent": sent, "failed": failed}