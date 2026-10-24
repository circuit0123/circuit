"""POST /api/beta/redeem: one answer for every bad code, a row lock on the last use, org codes, rate limits."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.beta import services
from apps.beta.models import BetaAccess, InviteCode
from apps.events.models import Event
from core import ratelimit

pytestmark = pytest.mark.django_db
URL = "/api/beta/redeem"


def redeem(client, code):
    return client.post(URL, {"code": code})


def test_a_valid_code_lets_the_member_in(beta_on, make_member, make_code, client_for):
    m, code = make_member("student"), make_code()
    c = client_for(m)
    assert c.get("/api/matches").status_code == 403
    r = redeem(c, code.code)
    assert r.status_code == 200 and r.json() == {"beta_access": True, "organisation_id": None}
    assert c.get("/api/matches").status_code == 200
    code.refresh_from_db()
    assert code.uses == 1
    access = BetaAccess.objects.get(member=m)
    assert access.source == "code" and access.invite_code_id == code.pk
    assert Event.objects.filter(type="beta.access_granted", actor=m).exists()


def test_typing_habits_are_forgiven(beta_on, make_member, make_code, client_for):
    code = make_code()
    spaced = f" {code.code[:5].lower()}-{code.code[5:].lower()} "
    assert redeem(client_for(make_member("student")), spaced).status_code == 200


def bad_codes(make_code):
    expired = make_code(days=1)
    InviteCode.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    used_up = make_code(max_uses=1)
    InviteCode.objects.filter(pk=used_up.pk).update(uses=1)
    revoked = make_code()
    services.revoke_code(revoked)
    return {
        "unknown": "ABCDEFGHJK",
        "wrong shape": "X",
        "empty": "",
        "sql-ish": "' OR 1=1 --",
        "expired": expired.code,
        "used up": used_up.code,
        "revoked": revoked.code,
    }


def test_every_bad_code_gets_the_identical_answer(beta_on, make_member, make_code, client_for):
    """Same status and the very same body bytes, so nothing (not even a field) tells the cases apart."""
    answers = {}
    for label, code in bad_codes(make_code).items():
        r = redeem(client_for(make_member("student")), code)
        answers[label] = (r.status_code, r.content)
    assert len(answers) == 7 and len(set(answers.values())) == 1
    status, body = next(iter(answers.values()))
    assert status == 400 and b"invalid_code" in body
    assert not BetaAccess.objects.exists()


def test_a_revoked_member_cannot_come_back_with_a_fresh_code(beta_on, make_member, make_code, client_for, let_in):
    m = make_member("student")
    access = let_in(m)
    access.revoked_at = timezone.now()
    access.save()
    fresh = make_code()
    r = redeem(client_for(m), fresh.code)
    assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_code")
    fresh.refresh_from_db()
    assert fresh.uses == 0


def test_someone_already_in_uses_up_nothing(beta_on, make_member, make_code, client_for, let_in):
    m, code = make_member("student"), make_code()
    let_in(m)
    assert redeem(client_for(m), code.code).status_code == 200
    assert redeem(client_for(m), "garbage").status_code == 200  # no oracle either way
    code.refresh_from_db()
    assert code.uses == 0


def test_redeeming_twice_uses_the_code_once(beta_on, make_member, make_code, client_for):
    m, code = make_member("student"), make_code(max_uses=5)
    c = client_for(m)
    assert redeem(c, code.code).status_code == redeem(c, code.code).status_code == 200
    code.refresh_from_db()
    assert code.uses == 1


def test_multi_use_code_stops_at_its_cap(beta_on, make_member, make_code, client_for):
    code = make_code(max_uses=2)
    statuses = [redeem(client_for(make_member("student")), code.code).status_code for _ in range(3)]
    assert statuses == [200, 200, 400]


def test_redemptions_are_listed_on_the_code(beta_on, make_member, make_code, client_for):
    code = make_code(max_uses=2)
    a, b = make_member("student"), make_member("student")
    redeem(client_for(a), code.code)
    redeem(client_for(b), code.code)
    assert set(code.redemptions.values_list("member_id", flat=True)) == {a.pk, b.pk}


# -- the race for the last use -----------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_two_people_racing_for_the_last_use_give_exactly_one_success(make_member, make_code):
    code = make_code(max_uses=1)
    members = [make_member("student") for _ in range(2)]
    barrier, results = threading.Barrier(2), []

    def attempt(member):
        try:
            barrier.wait(timeout=10)
            services.redeem(member, code.code)
            results.append("ok")
        except services.InvalidCode:
            results.append("invalid")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(m,)) for m in members]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert sorted(results) == ["invalid", "ok"]
    code.refresh_from_db()
    assert code.uses == 1 and BetaAccess.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_one_member_redeeming_two_codes_at_once_is_safe(make_member, make_code):
    a, b = make_code(), make_code()
    m = make_member("student")
    barrier, results = threading.Barrier(2), []

    def attempt(code):
        try:
            barrier.wait(timeout=10)
            services.redeem(m, code.code)
            results.append("ok")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(c,)) for c in (a, b)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert results == ["ok", "ok"] and BetaAccess.objects.filter(member=m).count() == 1
    used = InviteCode.objects.filter(pk__in=[a.pk, b.pk]).values_list("uses", flat=True)
    assert sum(used) == 1  # the second request saw the first one's access and spent nothing


# -- organisation codes ------------------------------------------------------------------------------
def test_an_org_code_joins_the_organisation(beta_on, make_member, make_org, make_code, client_for):
    org, m = make_org(), make_member("student")
    r = redeem(client_for(m), make_code(organisation=org).code)
    assert r.status_code == 200 and r.json()["organisation_id"] == org.pk
    m.refresh_from_db()
    assert m.organisation_id == org.pk and m.visible_to_org is False
    assert Event.objects.filter(type="org.joined", actor=m, payload__method="invite").exists()


def test_an_org_code_does_not_move_someone_who_already_has_an_organisation(beta_on, make_member, make_org, make_code, client_for):
    mine, other = make_org("Mine"), make_org("Other")
    m = make_member("student", org=mine)
    r = redeem(client_for(m), make_code(organisation=other).code)
    assert r.status_code == 200 and r.json()["organisation_id"] == mine.pk
    m.refresh_from_db()
    assert m.organisation_id == mine.pk
    assert BetaAccess.objects.filter(member=m).exists()


def test_a_code_without_organisation_leaves_it_alone(beta_on, make_member, make_code, client_for):
    m = make_member("student")
    redeem(client_for(m), make_code().code)
    m.refresh_from_db()
    assert m.organisation_id is None


# -- rate limits -----------------------------------------------------------------------------------
def test_per_member_limit(beta_on, settings, make_member, client_for):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "redeem": (3, 3600)}
    c = client_for(make_member("student"))
    assert [redeem(c, "ABCDEFGHJK").status_code for _ in range(4)] == [400, 400, 400, 429]
    assert redeem(c, "ABCDEFGHJK").json()["error"]["code"] == "rate_limited"


def test_per_address_limit_covers_many_accounts(beta_on, settings, make_member, client_for):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "redeem_ip": (3, 3600)}
    statuses = [redeem(client_for(make_member("student")), "ABCDEFGHJK").status_code for _ in range(4)]
    assert statuses == [400, 400, 400, 429]


def test_a_different_address_has_its_own_bucket(beta_on, settings, make_member, client_for):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "redeem_ip": (1, 3600)}
    c = client_for(make_member("student"))
    assert c.post(URL, {"code": "X"}, REMOTE_ADDR="10.0.0.1").status_code == 400
    assert c.post(URL, {"code": "X"}, REMOTE_ADDR="10.0.0.1").status_code == 429
    assert c.post(URL, {"code": "X"}, REMOTE_ADDR="10.0.0.2").status_code == 400


def test_anonymous_gets_401(client_for):
    assert redeem(client_for(), "ABCDEFGHJK").status_code == 401


# -- the client address -------------------------------------------------------------------------------
def test_client_ip_ignores_forwarded_for_without_a_trusted_proxy(rf, settings):
    settings.TRUSTED_PROXY_HOPS = 0
    req = rf.get("/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="6.6.6.6")
    assert ratelimit.client_ip(req) == "10.0.0.9"


def test_client_ip_takes_the_entry_the_trusted_proxy_appended(rf, settings):
    settings.TRUSTED_PROXY_HOPS = 1
    req = rf.get("/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7")  # the left part is attacker-written
    assert ratelimit.client_ip(req) == "203.0.113.7"
    settings.TRUSTED_PROXY_HOPS = 2
    assert ratelimit.client_ip(req) == "6.6.6.6"


def test_a_spoofed_header_cannot_dodge_the_limit(beta_on, settings, make_member, client_for):
    settings.TRUSTED_PROXY_HOPS = 1
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "redeem_ip": (1, 3600)}
    c = client_for(make_member("student"))
    a = c.post(URL, {"code": "X"}, HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.7")
    b = c.post(URL, {"code": "X"}, HTTP_X_FORWARDED_FOR="2.2.2.2, 203.0.113.7")
    assert (a.status_code, b.status_code) == (400, 429)


def test_garbage_in_the_header_falls_back_to_the_socket_address(rf, settings):
    settings.TRUSTED_PROXY_HOPS = 1
    req = rf.get("/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="not-an-ip")
    assert ratelimit.client_ip(req) == "10.0.0.9"


def test_the_ip_bucket_name_holds_no_raw_address(rf):
    req = rf.get("/", REMOTE_ADDR="203.0.113.7")
    assert "203" not in ratelimit.ip_key(req) and ratelimit.ip_key(req).startswith("ip-")
