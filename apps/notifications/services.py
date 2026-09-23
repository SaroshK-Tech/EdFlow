"""Notification side-effects — always guarded, never raise (offline-first)."""

from django.contrib.auth import get_user_model

from .models import Audience, Notification


def recipients_for(audience, klass=None):
    """Active users that an announcement of the given audience targets."""
    User = get_user_model()
    qs = User.objects.filter(is_active=True)
    if audience in (Audience.STAFF, Audience.TEACHERS):
        qs = qs.filter(is_staff=True)
    elif audience == Audience.CLASS:
        qs = qs.filter(is_staff=True)
    return qs


def notify_announcement(announcement, actor=None):
    """Create per-user Notification rows for an announcement (best-effort)."""
    created = 0
    for user in recipients_for(announcement.audience, announcement.klass):
        if actor and user.pk == actor.pk:
            continue
        Notification.objects.create(
            recipient=user,
            announcement=announcement,
            text=f"New announcement: {announcement.title}",
            url=f"/notifications/announcements/{announcement.pk}/",
            icon="megaphone",
        )
        created += 1
    return created


def notify_user(user, text, url="", icon="bell", announcement=None):
    try:
        return Notification.objects.create(
            recipient=user,
            announcement=announcement,
            text=text,
            url=url,
            icon=icon,
        )
    except Exception:
        return None