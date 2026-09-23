"""Celery task for notification fan-out (spec §24/§29)."""

from celery import shared_task

from apps.core.realtime import notify_user as realtime_notify_user


@shared_task
def broadcast_announcement(announcement_pk, actor_pk=None):
    """Create Notification rows (guarded) and push realtime events."""
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.notifications.models import Audience
    from .services import recipients_for, notify_announcement, notify_user
    from .models import Announcement

    try:
        announcement = Announcement.objects.get(pk=announcement_pk)
    except Announcement.DoesNotExist:
        return {"status": "skipped", "reason": "announcement missing"}

    actor = None
    if actor_pk:
        actor = get_user_model().objects.filter(pk=actor_pk).first()
    created = notify_announcement(announcement, actor=actor)

    detail_url = reverse("notifications:announcement_detail", kwargs={"pk": announcement.pk})
    for user in recipients_for(announcement.audience, announcement.klass):
        if actor and user.pk == actor.pk:
            continue
        notify_user(
            user,
            f"New announcement: {announcement.title}",
            detail_url,
            "megaphone",
            announcement,
        )
        realtime_notify_user(user, "announcement.published", {"title": announcement.title, "url": detail_url})
    return {"created": created}