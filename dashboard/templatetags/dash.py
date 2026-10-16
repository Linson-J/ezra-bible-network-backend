from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def ago(value):
    """Compact relative time: 'just now', '5m ago', '3h ago', '2d ago', else '12 Mar'."""
    if not value:
        return ""
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 7 * 86400:
        return f"{int(seconds // 86400)}d ago"
    local = timezone.localtime(value)
    return local.strftime("%-d %b" if local.year == timezone.localdate().year else "%-d %b %Y")


@register.filter
def duration(minutes):
    """90 -> '1h 30m'."""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if h and m else f"{h}h" if h else f"{m}m"
