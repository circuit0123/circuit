"""Small daily counters kept in Postgres (not Redis: Redis is disposable and a cap that forgets itself is no cap).

    usage.bump("llm_calls")          # +1 for today (India day), returns the new total
    usage.total("llm_calls", days=30)

The increment is one INSERT ... ON CONFLICT DO UPDATE, so any number of instances count without losing a call.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection
from django.db.models import Sum
from django.utils import timezone

from core.models import UsageCounter


def today(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(ZoneInfo(settings.NOTIFICATION_TZ)).date()


def bump(name: str, by: int = 1, day: date | None = None) -> int:
    table = UsageCounter._meta.db_table
    with connection.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table} (name, day, count) VALUES (%s, %s, %s) "  # noqa: S608 (table name from the model)
            f"ON CONFLICT (name, day) DO UPDATE SET count = {table}.count + EXCLUDED.count RETURNING count",
            [name, day or today(), by],
        )
        return int(cur.fetchone()[0])


def count(name: str, day: date | None = None) -> int:
    row = UsageCounter.objects.filter(name=name, day=day or today()).values_list("count", flat=True).first()
    return int(row or 0)


def total(name: str, days: int = 30, now: datetime | None = None) -> int:
    """Sum over the last `days` India days, today included."""
    since = today(now) - timedelta(days=days - 1)
    return int(UsageCounter.objects.filter(name=name, day__gte=since).aggregate(n=Sum("count"))["n"] or 0)
