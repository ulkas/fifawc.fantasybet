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
