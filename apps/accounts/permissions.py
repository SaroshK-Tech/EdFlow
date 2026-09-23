from functools import wraps

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

User = get_user_model()


def role_required(*role_keys):
    """Restrict a view to users with one of the given role keys.

    Superusers bypass the check. Raise 403 otherwise.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_authenticated and (
                user.is_superuser
                or (user.role and user.role.key in role_keys)
            ):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return _wrapped

    return decorator


def login_required_roles(*role_keys):
    """Like role_required but redirects anonymous users to login first."""
    from django.contrib.auth.decorators import login_required

    return login_required(role_required(*role_keys))