from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import SafeString

register = template.Library()


@register.filter
def getitem(mapping, key):
    """Dict/object lookup from templates, e.g. stats.routine_grid|getitem:klass|getitem:period."""
    if mapping is None:
        return None
    try:
        return mapping[key] if isinstance(mapping, dict) else getattr(mapping, str(key))
    except (KeyError, TypeError, AttributeError):
        return None


@register.simple_tag
def url_or_empty(name, arg=None):
    """Reverse a named URL, returning an empty string if it is not registered.

    Keeps shared layout safe while a module is mid-build (spec §28 shell).
    """
    try:
        if arg:
            return reverse(name, args=[arg])
        return reverse(name)
    except NoReverseMatch:
        return SafeString("")