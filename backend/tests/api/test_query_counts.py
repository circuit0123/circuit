"""Query budgets for the busiest endpoints, on the seeded demo world (300 members, 150 startups, 66 jobs).

Two things are checked per endpoint: it stays under a fixed budget, and asking for a bigger page costs the same number of queries
(so a loop that queries once per row, an N+1, fails here long before it shows up as a slow page under load).
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.matching import services as matching
from seed.build import run
from seed.personas import auth_uuid

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings):
    settings.FEATURES = "pulse:everyone,daily_drop:everyone,circuits:everyone"
    run(settings.SEED_CITY)
    matching.compute_all()
    from django.utils import timezone

    from apps.accounts.models import Member
    from apps.social.drop import build_for, drop_day

    me = Member.objects.get(auth_user_id=auth_uuid("ravi"))
    build_for(me, drop_day(timezone.now()))
    return me


def queries(client, path):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(path)
    assert response.status_code == 200, (path, response.status_code, response.content[:200])
    return len(ctx), response.json()


# (path, budget). A budget is the measured count plus some room; lower it when an endpoint gets cheaper. Live wire is the heaviest
# (37) because it merges five kinds of update; it was 52 before its per-person mutual-connection query became one query.
BUDGETS = {
    "/api/me": 8,
    "/api/drop/today": 20,
    "/api/livewire": 40,
    "/api/pulse?limit=20": 35,
    "/api/matches?limit=20": 14,
    "/api/jobs?limit=20": 10,
    "/api/startups/nearby": 8,
    "/api/search?q=ai": 14,
    "/api/conversations?folder=chats": 8,
    "/api/conversations/unread-count": 10,
    "/api/notifications": 8,
    "/api/startups/map?min_lng=80.1&min_lat=12.9&max_lng=80.4&max_lat=13.2": 8,
}


def test_every_busy_endpoint_stays_inside_its_query_budget(world, client_for):
    client = client_for(world)  # one seeded world for all of them: seeding is the slow part
    over = []
    for path, budget in sorted(BUDGETS.items()):
        queries(client, path)  # the first call warms caches (feature flags, content types) so the next count is the steady state
        n, _ = queries(client, path)
        if n > budget:
            over.append(f"{path} used {n} queries (budget {budget})")
    assert not over, "\n".join(over)


def test_a_bigger_page_costs_the_same_queries(world, client_for):
    client = client_for(world)
    pairs = [("/api/matches?limit=3", "/api/matches?limit=20"), ("/api/jobs?limit=3", "/api/jobs?limit=20"),
             ("/api/pulse?limit=3", "/api/pulse?limit=20")]  # fmt: skip
    for small, large in pairs:
        queries(client, small)
        n_small, small_body = queries(client, small)
        n_large, large_body = queries(client, large)
        assert len(large_body["items"]) > len(small_body["items"]), (
            f"{large}: the world is too small for this check to mean anything"
        )
        assert n_large <= n_small + 1, f"{large}: {n_large} queries vs {n_small} for a smaller page: one query per row"
