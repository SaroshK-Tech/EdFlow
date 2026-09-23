def site_context(request):
    """Inject global template context: school profile + nav badge counts."""
    from apps.school.models import SchoolProfile

    school = None
    if not request.path.startswith("/admin/"):
        school = SchoolProfile.objects.first()
    return {
        "school": school,
        "current_year": __import__("django.utils.timezone", fromlist=["now"]).now().year,
        "notifications": _recent_activity_notifications(request),
    }


class _NotificationFeed(list):
    """List subclass to carry unread_count attribute (Python 3.14 compatible)."""
    def __init__(self, *args, unread_count=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.unread_count = unread_count


def _recent_activity_notifications(request):
    """Topbar feed: real per-user notifications first, audit activity as fallback."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return _NotificationFeed(unread_count=0)
    try:
        from apps.notifications.models import Notification

        feed = _NotificationFeed()
        unread_count = 0
        for note in Notification.objects.filter(recipient=request.user).order_by("-created_at")[:6]:
            is_unread = not note.is_read
            if is_unread:
                unread_count += 1
            feed.append(
                {
                    "pk": note.pk,
                    "text": note.text,
                    "url": note.url or "/",
                    "icon": note.icon or "bell",
                    "unread": is_unread,
                }
            )
        if feed:
            feed.unread_count = unread_count
            return feed
    except Exception:
        pass

    from apps.core.models import AuditLog

    feed = _NotificationFeed(unread_count=0)
    logs = AuditLog.objects.exclude(user=request.user).order_by("-created_at")[:5]
    for log in logs:
        actor = log.user.get_full_name() if log.user else "System"
        feed.append(
            {
                "pk": log.pk,
                "text": f"{actor}: {log.action}",
                "url": "/",
                "icon": "activity",
            }
        )
    if not feed:
        feed.append(
            {
                "pk": 0,
                "text": "Welcome to EdFlow — everything is running offline-first.",
                "url": "/",
                "icon": "check-circle",
            }
        )
    return feed