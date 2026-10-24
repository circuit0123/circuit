from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Connection
from apps.circuits.models import Circuit
from apps.events.services import record
from apps.notifications.models import Notification
from core import flags
from tests.api.test_circuits import make_loop

pytestmark = pytest.mark.django_db
OFF = "pulse:off,daily_drop:off,circuits:off"


def only(settings, **audiences):
    settings.FEATURES = ",".join(f"{n}:{audiences.get(n, 'off')}" for n in flags.FLAGS)


# -- /api/config -----------------------------------------------------------------------------
def test_config_is_public_and_lists_every_flag(client_for):
    body = client_for().get("/api/config").json()
    assert body["env"] == "dev" and body["beta_mode"] is False
    assert body["features"] == dict.fromkeys(flags.FLAGS, True)


def test_config_depends_on_who_asks(settings, client_for, make_member):
    only(settings, pulse="everyone", circuits="testers")
    tester, other = make_member("student", is_tester=True), make_member("student")
    assert client_for().get("/api/config").json()["features"]["circuits"] is False
    assert client_for(other).get("/api/config").json()["features"]["circuits"] is False
    f = client_for(tester).get("/api/config").json()["features"]
    assert f["circuits"] is True and f["pulse"] is True and f["daily_drop"] is False


def test_a_bad_token_is_just_anonymous(settings, client_for):
    only(settings, circuits="testers")
    r = client_for().get("/api/config", HTTP_AUTHORIZATION="Bearer not-a-token")
    assert r.status_code == 200 and r.json()["features"]["circuits"] is False


# -- endpoints: 404 feature_off, testers audience works --------------------------------------
ENDPOINTS = {
    "pulse": [
        ("get", "/api/pulse"),
        ("post", "/api/pulse/seen"),
        ("get", "/api/livewire"),
        ("get", "/api/posts/1"),
        ("get", "/api/posts/1/replies"),
        ("get", "/api/members/1/posts"),
    ],  # fmt: skip
    "daily_drop": [("get", "/api/drop/today")],
    "circuits": [("get", "/api/circuits"), ("get", "/api/circuits/1")],
}


@pytest.mark.parametrize("flag", ENDPOINTS)
def test_off_means_404_feature_off(flag, settings, client_for, make_member):
    me = make_member("student")
    only(settings)
    for method, path in ENDPOINTS[flag]:
        r = getattr(client_for(me), method)(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "feature_off", path


@pytest.mark.parametrize("flag", ENDPOINTS)
def test_off_still_asks_who_you_are_first(flag, settings, client_for):
    only(settings)
    for method, path in ENDPOINTS[flag]:
        assert getattr(client_for(), method)(path).status_code == 401, path


@pytest.mark.parametrize("flag", ENDPOINTS)
def test_testers_audience_reaches_testers_only(flag, settings, client_for, make_member):
    only(settings, **{flag: "testers"})
    tester, other = make_member("student", is_tester=True), make_member("student")
    method, path = ENDPOINTS[flag][0]
    assert getattr(client_for(other), method)(path).status_code == 404
    assert getattr(client_for(tester), method)(path).status_code == 200


@pytest.mark.parametrize("flag", ENDPOINTS)
def test_everyone_audience_reaches_everyone(flag, settings, client_for, make_member):
    only(settings, **{flag: "everyone"})
    method, path = ENDPOINTS[flag][0]
    assert getattr(client_for(make_member("student")), method)(path).status_code == 200


def test_post_writes_are_flagged_too(settings, client_for, make_member):
    me = make_member("student")
    only(settings)
    r = client_for(me).post("/api/posts", {"body": "hi", "visibility": "everyone", "image_ids": []})
    assert r.status_code == 404 and r.json()["error"]["code"] == "feature_off"


def test_core_features_ignore_flags(settings, client_for, make_member):
    me = make_member("student")
    only(settings)
    for path in ("/api/me", "/api/matches", "/api/connections", "/api/conversations", "/api/notifications", "/api/jobs"):
        assert client_for(me).get(path).status_code == 200, path


# -- feeds, notifications, jobs --------------------------------------------------------------
def test_closed_circuits_leave_pulse_and_live_wire_when_circuits_is_off(settings, client_for, make_member, lists):
    asha, priya, arjun = make_loop(make_member)
    from apps.circuits.services import run_round

    run_round()
    circuit = Circuit.objects.get()
    for m in (asha, priya, arjun):
        for o in (asha, priya, arjun):
            if m.pk < o.pk:
                Connection.objects.get_or_create(member_a=m, member_b=o)
    record("circuit.completed", target_type="circuit", target_id=circuit.pk)

    def kinds():
        pulse = [i["activity"]["type"] for i in client_for(asha).get("/api/pulse").json()["items"] if i["kind"] == "activity"]
        wire = [i["kind"] for i in client_for(asha).get("/api/livewire").json()]
        return pulse, wire

    assert "circuit_completed" in kinds()[0]
    only(settings, pulse="everyone")
    assert "circuit_completed" not in kinds()[0] and "circuit_closed" not in kinds()[1]


def test_notifications_of_a_switched_off_feature_are_hidden_not_deleted(settings, client_for, make_member):
    me = make_member("student")
    Notification.objects.create(member=me, kind="circuit.proposed", payload={"circuit_id": 1})
    Notification.objects.create(member=me, kind="post.reply", payload={"post_id": 1})
    Notification.objects.create(member=me, kind="intro.received", payload={})
    c = client_for(me)
    assert c.get("/api/notifications/unread-count").json() == {"count": 3}
    only(settings)
    assert c.get("/api/notifications/unread-count").json() == {"count": 1}
    assert [n["kind"] for n in c.get("/api/notifications").json()["items"]] == ["intro.received"]
    assert c.post("/api/notifications/read-all").json() == {"count": 1}
    assert Notification.objects.filter(member=me).count() == 3 and Notification.objects.filter(read_at__isnull=True).count() == 2


def test_the_daily_drop_job_does_nothing_when_its_flag_is_off(settings, capsys, make_member):
    make_member("student")
    only(settings)
    call_command("build_daily_drops")
    assert "skipped: flag off" in capsys.readouterr().out
    from apps.social.models import DailyDrop

    assert not DailyDrop.objects.exists()
    only(settings, daily_drop="everyone")
    call_command("build_daily_drops")
    assert "flag off" not in capsys.readouterr().out


def test_the_circuit_round_job_does_nothing_when_its_flag_is_off(settings, capsys, make_member, lists):
    from apps.circuits.models import CircuitRound

    make_loop(make_member)
    only(settings)
    call_command("run_circuit_round")
    assert "skipped: flag off" in capsys.readouterr().out and not CircuitRound.objects.exists()
    only(settings, circuits="everyone")
    call_command("run_circuit_round")
    assert Circuit.objects.count() == 1


def test_an_in_flight_circuit_still_expires_with_the_flag_off(settings, make_member, lists):
    from apps.circuits.services import run_round

    make_loop(make_member)
    run_round()
    Circuit.objects.update(consent_deadline=timezone.now() - timedelta(hours=1))
    only(settings)
    call_command("expire_items")
    assert Circuit.objects.get().status == "expired"


def test_matching_is_identical_whatever_the_flags(settings, make_member, lists):
    from apps.matching.models import MatchResult

    make_loop(make_member)

    def snapshot():
        call_command("compute_matches")
        return sorted(MatchResult.objects.values_list("member_id", "candidate_id", "score", "is_bridge"))

    on = snapshot()
    only(settings)
    assert snapshot() == on and on
