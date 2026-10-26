"""Sign-up funnel per source (`src`): clicks -> signed up -> beta access -> onboarding done -> first match action.

Counts only. Each step after "clicks" counts members who signed up in the window, so the steps read left to right as a funnel.
Any count under DASHBOARD_MIN_COUNT is hidden, as on the partner dashboard, and nothing identifies a person.
"""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.accounts.models import Member
from apps.beta.models import JoinVisit
from apps.dashboard.services import count
from apps.events.models import Event

STEPS = ("clicks", "signed_up", "beta_access", "onboarding_done", "first_match_action")
FIRST_ACTION_EVENTS = ("intro.requested", "drop.swiped", "connection.requested")  # the first thing done with a match
NO_SOURCE = "(none)"


def _by_src(rows) -> dict[str, int]:
    return {src: n for src, n in rows}


def funnel(days: int | None = None) -> list[dict]:
    """One row per source: {"src": ..., "clicks": {"value", "hidden"}, ...}, biggest first. `days` limits to the last N days."""
    since = timezone.now() - timedelta(days=days) if days else None
    members = Member.objects.filter(is_simulated=False, deleted_at__isnull=True)
    visits = JoinVisit.objects.all()
    if since:
        members = members.filter(created_at__gte=since)
        visits = visits.filter(day__gte=since.date())

    def per_src(qs) -> dict[str, int]:
        return _by_src(qs.values_list("signup_source").annotate(n=Count("pk")).order_by())

    acted_ids = Event.objects.filter(type__in=FIRST_ACTION_EVENTS, actor__in=members).values("actor")
    totals = {
        "clicks": _by_src(visits.values_list("src").annotate(n=Sum("count")).order_by()),
        "signed_up": per_src(members),
        "beta_access": per_src(members.filter(beta__isnull=False, beta__revoked_at__isnull=True)),
        "onboarding_done": per_src(members.filter(onboarding__completed_at__isnull=False)),
        "first_match_action": per_src(members.filter(pk__in=acted_ids)),
    }
    sources = set().union(*(t.keys() for t in totals.values()))
    rows = [{"src": src or NO_SOURCE, **{step: count(totals[step].get(src, 0)) for step in STEPS}} for src in sources]
    size = {src or NO_SOURCE: totals["signed_up"].get(src, 0) for src in sources}
    rows.sort(key=lambda r: (-size[str(r["src"])], str(r["src"])))
    return rows


def render(rows: list[dict]) -> str:
    def cell(c: dict) -> str:
        return "<5" if c["hidden"] else str(c["value"])

    out = [f"{'source':28}" + "".join(f"{s:>20}" for s in STEPS)]
    out += [f"{r['src']:28}" + "".join(f"{cell(r[s]):>20}" for s in STEPS) for r in rows]
    return "\n".join(out) if rows else "No sign-ups or clicks yet."
