"""B7 part 1: a member who just finished sign-up gets their first Daily Drop within minutes (the first_drops job)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.events.models import Event
from apps.matching.models import Capability, MatchResult, Need, Offer
from apps.social.drop import build_first_drops, drop_day
from apps.social.models import DailyDrop

pytestmark = pytest.mark.django_db


def finish_signup(m, when=None):
    m.onboarding = {"completed_at": (when or timezone.now()).isoformat(), "answers": {}}
    m.save(update_fields=["onboarding", "updated_at"])


@pytest.fixture
def newcomer(lists, make_member):
    """A newcomer who needs SEO, and an established mentor who offers it (matches were last computed before the newcomer joined)."""
    seo, dev = Capability.objects.get(slug="seo"), Capability.objects.get(slug="frontend-dev")
    mentor = make_member("mentor", display_name="Lakshmi", city="Chennai")
    Offer.objects.create(member=mentor, capability=seo)
    Need.objects.create(member=mentor, capability=dev)
    new = make_member("student", display_name="Ravi", city="Chennai")
    Need.objects.create(member=new, capability=seo)
    Offer.objects.create(member=new, capability=dev)  # a fit in both directions is what scores "good"
    finish_signup(new)
    return new, mentor


def test_a_new_member_gets_matches_and_a_drop(newcomer):
    new, mentor = newcomer
    assert not MatchResult.objects.filter(member=new).exists()
    result = build_first_drops()
    assert result["waiting"] == 1 and result["built"] == 1
    drop = DailyDrop.objects.get(member=new, date=drop_day(timezone.now()))
    assert [c["member_id"] for c in drop.candidates] == [mentor.pk]
    assert Event.objects.filter(type="drop.first_attempted", actor=new).count() == 1


def test_the_new_member_sees_the_drop_in_the_app(newcomer, client_for):
    new, mentor = newcomer
    c = client_for(new)
    before = c.get("/api/drop/today").json()
    assert before["cards"] == []
    build_first_drops()
    after = c.get("/api/drop/today").json()
    assert [card["member"]["id"] for card in after["cards"]] == [mentor.pk]


def test_next_drop_at_says_in_a_few_minutes_while_the_first_one_is_pending(newcomer, client_for):
    new, _ = newcomer
    soon = client_for(new).get("/api/drop/today").json()["next_drop_at"]
    from datetime import datetime

    delta = datetime.fromisoformat(soon) - timezone.now()
    assert timedelta(minutes=4) < delta <= timedelta(minutes=5, seconds=5)
    build_first_drops()
    after = datetime.fromisoformat(client_for(new).get("/api/drop/today").json()["next_drop_at"])
    assert after - timezone.now() > timedelta(minutes=30)  # tomorrow at 08:00 once it has been built


def test_each_member_is_tried_once_even_with_nobody_to_meet(lists, make_member):
    lonely = make_member("student")
    finish_signup(lonely)
    assert build_first_drops() == {"day": drop_day(timezone.now()), "waiting": 1, "built": 0}
    assert build_first_drops()["waiting"] == 0  # no retry every five minutes
    assert Event.objects.get(type="drop.first_attempted", actor=lonely).payload == {"built": False}


def test_running_it_again_builds_nothing_twice(newcomer):
    build_first_drops()
    assert build_first_drops()["built"] == 0
    assert DailyDrop.objects.count() == 1


def test_only_recent_adult_real_members_who_finished_sign_up_qualify(lists, make_member):
    old = make_member("student")
    finish_signup(old, timezone.now() - timedelta(days=3))
    unfinished = make_member("student")
    kid = make_member("student", is_minor=True)
    finish_signup(kid)
    sim = make_member("student", is_simulated=True)
    finish_signup(sim)
    admin = make_member("partner_admin")
    finish_signup(admin)
    suspended = make_member("student")
    finish_signup(suspended)
    suspended.suspended_at = timezone.now()
    suspended.save()
    assert build_first_drops()["waiting"] == 0
    assert unfinished.pk  # created, never finished


def test_a_malformed_timestamp_is_ignored(lists, make_member):
    m = make_member("student")
    m.onboarding = {"completed_at": "not a date"}
    m.save()
    assert build_first_drops()["waiting"] == 0


def test_other_members_matches_are_not_touched(newcomer):
    new, mentor = newcomer
    MatchResult.objects.create(member=mentor, candidate=new, score=0.9, reason="old", components={})
    build_first_drops()
    assert MatchResult.objects.get(member=mentor, candidate=new).reason == "old"


def test_the_command_does_nothing_with_the_flag_off_and_works_with_it_on(newcomer, settings, capsys):
    from core import flags

    new = newcomer[0]
    settings.FEATURES = ",".join(f"{n}:{'off' if n == 'daily_drop' else 'everyone'}" for n in flags.FLAGS)
    call_command("first_drops")
    out = capsys.readouterr().out
    assert "skipped" in out and not DailyDrop.objects.filter(member=new).exists()
    assert not Event.objects.filter(type="drop.first_attempted").exists()  # nothing was tried, so it is still waiting
    settings.FEATURES = ",".join(f"{n}:everyone" for n in flags.FLAGS)
    call_command("first_drops")
    assert "First drops: 1 waiting, 1 built" in capsys.readouterr().out
    assert DailyDrop.objects.filter(member=new).exists()
