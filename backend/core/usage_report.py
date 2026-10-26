"""Weekly free-tier usage report (`usage_report` job, Mondays 09:00 IST; `make usage-report`).

The free plans we depend on have hard limits that cost nothing until they are hit and then stop the app or send a bill. This checks
the ones the app can measure by itself, prints a table, and logs `usage.warning` for anything at USAGE_WARN_PCT (70%) or more. The
alert policy in infra/monitoring/ turns that line into a message on your phone, a week or more before the limit.

Measured here:      database size, storage size, sign-in accounts, emails (month and busiest day), Redis memory and commands, LLM calls.
NOT measurable here: Supabase egress, Vercel bandwidth, Cloud Run request quota. Check those in each dashboard (RUNBOOK.md,
"A free-tier limit is nearly hit"). The limits are FREE_TIER_LIMITS in settings; paid plans raise them through the env variable of
the same name.

A reading that cannot be taken (no storage schema on a laptop, Redis down) is shown as "n/a" and never raises.
"""

from dataclasses import dataclass

import structlog
from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from core import email as email_module
from core import ist, usage
from core.models import OutboundEmail

log = structlog.get_logger("usage")


@dataclass
class Reading:
    key: str  # matches a FREE_TIER_LIMITS key where there is one
    label: str
    used: float | None
    limit: float | None
    unit: str  # "MB" | "" | ...
    note: str = ""

    @property
    def pct(self) -> int | None:
        if self.used is None or not self.limit:
            return None
        return round(100 * self.used / self.limit)

    @property
    def warn(self) -> bool:
        return self.pct is not None and self.pct >= settings.USAGE_WARN_PCT

    def text(self) -> str:
        note = f" ({self.note})" if self.note else ""
        if self.used is None:
            return "n/a" + note
        scale = 1024**2 if self.unit == "MB" else 1
        used = f"{self.used / scale:,.1f}" if self.unit == "MB" else f"{self.used:,.0f}"
        limit = f" of {self.limit / scale:,.0f}" if self.limit else ""
        return f"{used}{limit}{' ' + self.unit if self.unit else ''}{note}"


def _limit(key: str) -> float | None:
    value = settings.FREE_TIER_LIMITS.get(key)
    return float(value) if value else None


def database_size() -> Reading:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database())")
        size = cur.fetchone()[0]
    return Reading("database_bytes", "Database size", float(size), _limit("database_bytes"), "MB")


def storage_size() -> Reading:
    """Supabase Storage keeps its file list in storage.objects. Not there on a laptop."""
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('storage.objects')")
        if cur.fetchone()[0] is None:
            return Reading(
                "storage_bytes", "File storage", None, _limit("storage_bytes"), "MB", "no Supabase storage schema here"
            )
        cur.execute("SELECT COALESCE(sum((metadata->>'size')::bigint), 0) FROM storage.objects")
        size = cur.fetchone()[0]
    return Reading("storage_bytes", "File storage", float(size), _limit("storage_bytes"), "MB")


def sign_in_accounts() -> Reading:
    from apps.accounts.models import Member

    n = Member.objects.filter(is_simulated=False, deleted_at__isnull=True).count()
    return Reading("auth_users", "Sign-in accounts (monthly active users are at most this)", float(n), _limit("auth_users"), "")


def emails() -> list[Reading]:
    used = email_module.usage()
    busiest = (
        OutboundEmail.objects.filter(status=OutboundEmail.Status.SENT, sent_at__gte=email_module.period_starts(timezone.now())[1])
        .annotate(d=TruncDate("sent_at", tzinfo=ist.tz()))
        .values("d")
        .annotate(n=Count("pk"))
        .order_by("-n")
        .first()
    )
    return [
        Reading("emails_month", "Emails sent this month", float(used["sent_month"]), _limit("emails_month"), ""),
        Reading("emails_day", "Emails, busiest day this month", float(busiest["n"] if busiest else 0), _limit("emails_day"), ""),
    ]


def redis_readings() -> list[Reading]:
    from core.cache import get_cache

    try:
        info = get_cache().client.info()
    except Exception as exc:
        note = type(exc).__name__
        return [
            Reading("redis_memory_bytes", "Redis memory", None, _limit("redis_memory_bytes"), "MB", note),
            Reading("redis_commands_month", "Redis commands", None, _limit("redis_commands_month"), "", note),
        ]
    memory = info.get("used_memory")
    commands = info.get("total_commands_processed")
    return [
        Reading("redis_memory_bytes", "Redis memory", float(memory) if memory is not None else None, _limit("redis_memory_bytes"), "MB"),
        Reading(
            "redis_commands_month", "Redis commands", float(commands) if commands is not None else None, _limit("redis_commands_month"), "",
            "total since Redis started; the exact monthly number is in the Upstash dashboard",
        ),
    ]  # fmt: skip


def llm_readings() -> list[Reading]:
    cap = settings.LLM_DAILY_CALL_LIMIT
    return [
        Reading(
            "llm_calls_today", "AI calls today", float(usage.count("llm_calls")), float(cap) if cap else None, "",
            f"{usage.total('llm_calls', 30):,} in the last 30 days" + ("" if cap else "; no daily cap set"),
        )
    ]  # fmt: skip


def collect() -> list[Reading]:
    readings: list[Reading] = []
    for step in (
        lambda: [database_size()],
        lambda: [storage_size()],
        lambda: [sign_in_accounts()],
        emails,
        redis_readings,
        llm_readings,
    ):
        try:
            readings += step()
        except Exception as exc:  # one broken measurement must not hide the others
            log.warning("usage.reading_failed", error=type(exc).__name__)
    return readings


def render(readings: list[Reading]) -> str:
    width = max(len(r.label) for r in readings)
    lines = [f"{'':2}{'WHAT':<{width}}  {'USED':<44} {'%':>4}"]
    for r in readings:
        mark = "!!" if r.warn else "  "
        pct = f"{r.pct}%" if r.pct is not None else "-"
        lines.append(f"{mark}{r.label:<{width}}  {r.text():<44} {pct:>4}")
    lines.append(
        f"\n!! = at {settings.USAGE_WARN_PCT}% or more of a free-tier limit. Not measured here: Supabase egress, Vercel bandwidth, Cloud Run quota."
    )
    return "\n".join(lines)


def run() -> tuple[list[Reading], dict]:
    readings = collect()
    log.info("usage.report", **{r.key: r.pct for r in readings if r.pct is not None})
    warnings = [r for r in readings if r.warn]
    for r in warnings:  # WARNING severity: the alert policy counts these lines
        log.warning("usage.warning", what=r.key, percent=r.pct)
    return readings, {"checked": len(readings), "warnings": len(warnings)}
