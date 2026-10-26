"""One search box over people, startups and roles (Discover, DESIGN.md §4).

Only names and titles are searched, never bios or private fields. People are limited to those the viewer could already see
elsewhere: hidden, under-18, suspended, deleted, simulated, admin and blocked members never show up, and an under-18 searcher
finds only their own connections. The rate limit and the 10-per-kind cap keep it from being used to list the whole membership.
"""

from django.db.models import Q

from apps.accounts.models import Member, Role
from apps.jobs.services import list_jobs_page
from apps.social import media
from apps.social.relations import blocked_ids, connected_ids
from apps.social.schemas import author
from apps.startups import services
from apps.startups.models import Startup
from core.ratelimit import check_rate

LIMIT = 10
MIN_CHARS = 2


def people(member: Member, text: str) -> list[dict]:
    qs = Member.objects.filter(
        display_name__icontains=text,
        suspended_at__isnull=True,
        deleted_at__isnull=True,
        is_minor=False,
        is_simulated=member.is_simulated,
        role__in=[Role.STUDENT, Role.FOUNDER, Role.MENTOR, Role.INVESTOR],
    ).exclude(Q(profile_visibility=Member.Visibility.HIDDEN) | Q(pk=member.pk) | Q(pk__in=blocked_ids(member.pk)))
    if member.is_minor:
        qs = qs.filter(pk__in=connected_ids(member.pk))  # an under-18 can find their own connections, nobody else
    found = list(qs.order_by("display_name", "id")[:LIMIT])
    media.prime_photos(found)
    return [author(m) for m in found]


def startups(member: Member, text: str) -> list[dict]:
    qs = Startup.objects.filter(
        Q(name__icontains=text) | Q(sector__icontains=text), location__isnull=False, hidden_at__isnull=True
    ).order_by("name", "id")
    return services._pins(member, list(qs[:LIMIT]))


def jobs(member: Member, text: str) -> list[dict]:
    return list_jobs_page(member, {"q": text}, 0, LIMIT)["items"]


def search(member: Member, text: str) -> dict:
    text = text.strip()
    if len(text) < MIN_CHARS:
        return {"people": [], "startups": [], "jobs": []}
    check_rate(member.pk, "search")
    return {"people": people(member, text), "startups": startups(member, text), "jobs": jobs(member, text)}
