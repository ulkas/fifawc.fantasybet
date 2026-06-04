from __future__ import annotations

from zoneinfo import ZoneInfo

from django import template
from django.conf import settings
from django.utils import timezone
from django.utils.dateformat import format as date_format

register = template.Library()


@register.filter
def cet_match_time(value, date_format_string: str = "M j, H:i") -> str:
    if value is None:
        return ""
    localized = timezone.localtime(value, ZoneInfo(settings.TIME_ZONE))
    return f"{date_format(localized, date_format_string)} CET"


@register.filter
def match_id(match) -> str:
    """Format match as 'Match A7' using group letter and match number."""
    if not match or not hasattr(match, 'match_number'):
        return ""
    group = getattr(match, 'group', '')
    if group:
        # Extract first letter from group name (e.g., "Group A" -> "A")
        group_letter = group.split()[-1] if group else ''
        if group_letter:
            return f"{group_letter}{match.match_number}"
    return str(match.match_number)
