"""India time, in one place. Servers run in UTC; members, the Daily Drop and quiet hours live in IST (settings.APP_TZ)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def tz() -> ZoneInfo:
    return ZoneInfo(settings.APP_TZ)


def local(now: datetime | None = None) -> datetime:
    return (now or timezone.now()).astimezone(tz())


def day(now: datetime | None = None) -> date:
    """The India calendar date."""
    return local(now).date()


def day_start(now: datetime | None = None) -> datetime:
    return local(now).replace(hour=0, minute=0, second=0, microsecond=0)
