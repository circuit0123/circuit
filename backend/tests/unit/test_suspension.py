"""A suspended member is locked out at once, on every route, even with a perfectly valid token."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Member
from apps.moderation.models import AuditLog
from core import auth
from tests.api.test_access_matrix import MATRIX, PUBLIC, call

pytestmark = pytest.mark.django_db


def suspend(member):
    member.suspended_at = timezone.now()
    member.save()


def test_suspended_member_is_403_in_the_standard_format(make_member, client_for):
    m = make_member()
    suspend(m)
    r = client_for(m).get("/api/me")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "account_suspended" and set(r.json()["error"]) == {"code", "message", "details"}


def test_suspension_takes_effect_on_the_next_request_and_can_be_lifted(make_member, client_for):
    m = make_member()
    c = client_for(m)
    assert c.get("/api/me").status_code == 200
    suspend(m)
    assert c.get("/api/me").status_code == 403  # same token, no waiting for it to expire
    m.suspended_at = None
    m.save()
    assert c.get("/api/me").status_code == 200


@pytest.mark.parametrize("route", sorted(MATRIX))
@pytest.mark.parametrize("role", ["student", "founder", "partner_admin", "super_admin"])
def test_suspended_member_cannot_use_any_route(route, role, make_member, make_org, client_for):
    m = make_member(role, org=make_org())
    suspend(m)
    r = call(client_for(m), *route)
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_suspended"
    m.refresh_from_db()
    assert m.organisation_id is not None  # nothing was changed on their behalf (e.g. a leave)


def test_suspended_demo_persona_is_locked_out_too(settings, make_member):
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    m = make_member("founder")
    suspend(m)
    r = Client().get("/api/me", HTTP_AUTHORIZATION=f"Bearer {auth.issue_demo_token(m.auth_user_id)}")
    assert r.status_code == 403


def test_suspended_member_is_not_listed_to_partner_admins(make_member, make_org, client_for):
    org = make_org()
    admin_m = make_member("partner_admin", org=org)
    ok = make_member(org=org, visible_to_org=True)
    gone = make_member(org=org, visible_to_org=True)
    suspend(gone)
    ids = [i["id"] for i in client_for(admin_m).get("/api/organisations/mine/members").json()["items"]]
    assert ids == [ok.pk]


def test_public_routes_still_work_for_everyone():
    for method, path in PUBLIC - {("POST", "/api/demo/token")}:
        assert Client().generic(method, path).status_code in (200, 404)


def admin_request(rf):
    staff = get_user_model().objects.create_superuser("mod", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    request._messages = CookieStorage(request)
    return request, staff


def test_admin_actions_suspend_and_reinstate_with_audit(rf, make_member, make_org):
    ma = admin.site._registry[Member]
    assert {"suspend_members", "reinstate_members"} <= set(ma.actions)
    m = make_member(org=make_org(), visible_to_org=True)
    request, staff = admin_request(rf)
    ma.suspend_members(request, Member.objects.filter(pk=m.pk))
    m.refresh_from_db()
    assert m.suspended_at is not None and m.visible_to_org is False
    assert AuditLog.objects.filter(actor=staff, action="suspend", target_id=str(m.pk)).exists()
    ma.reinstate_members(request, Member.objects.filter(pk=m.pk))
    m.refresh_from_db()
    assert m.suspended_at is None
    assert AuditLog.objects.filter(actor=staff, action="reinstate", target_id=str(m.pk)).exists()


def test_suspending_twice_does_not_reset_the_original_time(rf, make_member):
    m = make_member()
    request, _ = admin_request(rf)
    ma = admin.site._registry[Member]
    ma.suspend_members(request, Member.objects.filter(pk=m.pk))
    first = Member.objects.get(pk=m.pk).suspended_at
    ma.suspend_members(request, Member.objects.filter(pk=m.pk))
    assert Member.objects.get(pk=m.pk).suspended_at == first
