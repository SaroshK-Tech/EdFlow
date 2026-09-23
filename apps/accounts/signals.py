"""Authentication signals: record successful and failed login attempts.

Wired up in ``apps.py``. Backed by DB everywhere (offline-first); deleted in
TZ/geo corners with a defence-in-depth try/except.
"""

import logging

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import LoginHistory

logger = logging.getLogger(__name__)


def _client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _record(**kwargs):
    LoginHistory.objects.create(**kwargs)


@receiver(user_logged_in)
def _on_logged_in(sender, request, user, **kwargs):
    try:
        _record(
            user=user,
            username_attempted=(user.get_username() or "")[:150],
            succeeded=True,
            ip_address=_client_ip(request),
            user_agent=((request.META.get("HTTP_USER_AGENT") or "") if request else "")[:500],
        )
    except Exception as exc:  # pragma: no cover - never break login
        logger.warning("login history write failed: %s", exc)


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    try:
        _record(
            succeeded=False,
            username_attempted=str(credentials.get("username", "") or "")[:150],
            ip_address=_client_ip(request),
            user_agent=((request.META.get("HTTP_USER_AGENT") or "") if request else "")[:500],
        )
    except Exception as exc:  # pragma: no cover - never break login
        logger.warning("login history (fail) write failed: %s", exc)