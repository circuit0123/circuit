"""Django admin for the beta, the invite_codes command, and the startup rules. Every admin action leaves an audit_log row."""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage
from django.core import mail
from django.core.management import CommandError, call_command
from django.utils import timezone
from pydantic import ValidationError

from apps.beta import services
from apps.beta.admin import AllowlistForm, InviteCodeForm
from apps.beta.models import AllowlistEntry, BetaAccess, InviteCode, WaitlistEntry
from apps.moderation.models import AuditLog
from circuit.config import Config
from tests.unit.test_config import BASE

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(rf):
    user = get_user_model().objects.create_superuser("mod", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = user
    request._messages = CookieStorage(request)
    return SimpleNamespace(user=user, request=request)


def model_admin(model):
    return admin.site._registry[model]


# -- invite codes ------------------------------------------------------------------------------------
def test_creating_a_code_in_admin_generates_it_and_records_who(staff):
    ma = model_admin(InviteCode)
    obj = InviteCode(max_uses=5, note="for the pilot")
    ma.save_model(staff.request, obj, SimpleNamespace(changed_data=["max_uses", "note"]), change=False)
    obj.refresh_from_db()
    assert len(obj.code) == 10 and obj.kind == "admin" and obj.created_by_staff == staff.user and obj.max_uses == 5
    assert AuditLog.objects.filter(actor=staff.user, action="create", target_id=str(obj.pk)).exists()


def test_the_admin_form_cannot_set_the_code_or_lower_max_uses_below_uses(make_code):
    assert "code" not in InviteCodeForm.base_fields
    code = make_code(max_uses=3)
    InviteCode.objects.filter(pk=code.pk).update(uses=2)
    code.refresh_from_db()
    assert not InviteCodeForm({"max_uses": 1, "note": ""}, instance=code).is_valid()
    assert InviteCodeForm({"max_uses": 2, "note": ""}, instance=code).is_valid()
    assert not InviteCodeForm({"max_uses": 0, "note": ""}).is_valid()


def test_revoking_codes_is_audited_and_stops_new_uses(staff, make_code, make_member):
    ma = model_admin(InviteCode)
    code = make_code(max_uses=3)
    ma.revoke_codes(staff.request, InviteCode.objects.filter(pk=code.pk))
    code.refresh_from_db()
    assert code.revoked_at is not None
    assert AuditLog.objects.filter(actor=staff.user, action="invite.revoke", target_id=str(code.pk)).exists()
    with pytest.raises(services.InvalidCode):
        services.redeem(make_member("student"), code.code)
    n = AuditLog.objects.count()
    ma.revoke_codes(staff.request, InviteCode.objects.filter(pk=code.pk))
    assert AuditLog.objects.count() == n  # revoking again does nothing and logs nothing


def test_codes_cannot_be_deleted(staff, make_code):
    assert model_admin(InviteCode).has_delete_permission(staff.request, make_code()) is False


# -- waitlist ----------------------------------------------------------------------------------------
def test_approve_action_grants_access_emails_and_audits(
    staff, make_member, client_for, beta_on, django_capture_on_commit_callbacks
):
    ma = model_admin(WaitlistEntry)
    entry = WaitlistEntry.objects.create(email="wait@example.org", role="founder")
    with django_capture_on_commit_callbacks(execute=True):
        ma.approve_entries(staff.request, WaitlistEntry.objects.filter(pk=entry.pk))
    entry.refresh_from_db()
    assert entry.status == "approved" and entry.reviewed_by == staff.user and entry.reviewed_at
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["wait@example.org"]
    log = AuditLog.objects.get(action="waitlist.approve")
    assert log.actor == staff.user and log.target_id == str(entry.pk)
    assert "wait@example.org" not in str(log.payload)  # ids only
    # access: that person's verified sign-in email now passes the gate
    m = make_member("founder")
    assert client_for(m, email="wait@example.org").get("/api/matches").status_code == 200


def test_reject_action_sends_nothing_and_grants_nothing(
    staff, make_member, client_for, beta_on, django_capture_on_commit_callbacks
):
    ma = model_admin(WaitlistEntry)
    entry = WaitlistEntry.objects.create(email="no@example.org", role="student")
    with django_capture_on_commit_callbacks(execute=True):
        ma.reject_entries(staff.request, WaitlistEntry.objects.filter(pk=entry.pk))
    entry.refresh_from_db()
    assert entry.status == "rejected" and mail.outbox == []
    assert AuditLog.objects.filter(action="waitlist.reject", target_id=str(entry.pk)).exists()
    assert client_for(make_member("student"), email="no@example.org").get("/api/matches").status_code == 403


def test_reject_leaves_approved_entries_alone(staff):
    entry = WaitlistEntry.objects.create(email="in@example.org", role="student", status="approved")
    model_admin(WaitlistEntry).reject_entries(staff.request, WaitlistEntry.objects.all())
    entry.refresh_from_db()
    assert entry.status == "approved"


def test_waitlist_is_view_only_apart_from_the_actions(staff):
    ma = model_admin(WaitlistEntry)
    assert not ma.has_add_permission(staff.request) and not ma.has_change_permission(staff.request)


def test_waitlist_str_never_shows_the_address():
    assert "example.org" not in str(WaitlistEntry.objects.create(email="x@example.org", role="student"))


# -- allowlist ---------------------------------------------------------------------------------------
def test_allowlist_form_normalises_and_rejects_bad_or_duplicate_emails():
    assert AllowlistForm({"email": "  Friend@Example.ORG ", "note": ""}).is_valid()
    form = AllowlistForm({"email": "  Friend@Example.ORG ", "note": ""})
    form.is_valid()
    assert form.cleaned_data["email"] == "friend@example.org"
    for bad in ("nope", "a@b", "Kim@example.org", "two@example.org, three@example.org"):
        assert not AllowlistForm({"email": bad, "note": ""}).is_valid(), bad
    AllowlistEntry.objects.create(email="friend@example.org")
    assert not AllowlistForm({"email": "FRIEND@example.org", "note": ""}).is_valid()


def test_allowlist_changes_are_audited(staff):
    ma = model_admin(AllowlistEntry)
    obj = AllowlistEntry(email="friend@example.org")
    ma.save_model(staff.request, obj, SimpleNamespace(changed_data=["email"]), change=False)
    assert obj.added_by == staff.user and AuditLog.objects.filter(action="create", target_type="beta.allowlistentry").exists()
    ma.delete_model(staff.request, obj)
    assert AuditLog.objects.filter(action="delete", target_type="beta.allowlistentry").exists()


# -- access ------------------------------------------------------------------------------------------
def test_revoke_and_restore_access_are_audited_and_take_effect(staff, make_member, client_for, beta_on, let_in):
    ma = model_admin(BetaAccess)
    m = make_member("student")
    access = let_in(m)
    c = client_for(m)
    assert c.get("/api/matches").status_code == 200
    ma.revoke_access(staff.request, BetaAccess.objects.filter(pk=access.pk))
    access.refresh_from_db()
    assert access.revoked_at and access.revoked_by == staff.user
    assert AuditLog.objects.filter(action="beta.revoke", target_id=str(access.pk)).exists()
    assert c.get("/api/matches").status_code == 403
    ma.restore_access(staff.request, BetaAccess.objects.filter(pk=access.pk))
    assert AuditLog.objects.filter(action="beta.restore", target_id=str(access.pk)).exists()
    assert c.get("/api/matches").status_code == 200


def test_granting_by_hand_in_admin(staff, make_member):
    m = make_member("student")
    obj = BetaAccess(member=m)
    model_admin(BetaAccess).save_model(staff.request, obj, SimpleNamespace(changed_data=["member"]), change=False)
    assert BetaAccess.objects.get(member=m).source == "approved"
    assert model_admin(BetaAccess).has_delete_permission(staff.request, obj) is False


# -- manage.py invite_codes ---------------------------------------------------------------------------
def run_cmd(*args):
    out = StringIO()
    call_command("invite_codes", *args, stdout=out)
    return out.getvalue().splitlines()


def test_command_makes_n_codes_with_links_and_audits(settings):
    settings.APP_URL = "https://app.example"
    lines = run_cmd("--count", "4", "--uses", "3", "--days", "7", "--note", "pilot")
    assert len(lines) == 4
    codes = list(InviteCode.objects.order_by("id"))
    assert [ln.split()[0] for ln in lines] == [c.code for c in codes]
    assert all(ln.split()[1] == f"https://app.example/join?code={ln.split()[0]}&src=invite" for ln in lines)
    assert all(c.max_uses == 3 and c.note == "pilot" and c.kind == "admin" for c in codes)
    assert all(timedelta(days=6, hours=23) < c.expires_at - timezone.now() <= timedelta(days=7) for c in codes)
    log = AuditLog.objects.get(action="invite.create")
    assert log.payload["count"] == 4 and log.payload["via"] == "cli"


def test_command_org_code_and_bad_arguments(make_org):
    org = make_org()
    run_cmd("--org", str(org.pk))
    assert InviteCode.objects.get().organisation == org
    for args in (["--count", "0"], ["--count", "501"], ["--uses", "0"], ["--days", "0"], ["--org", "99999"]):
        with pytest.raises(CommandError):
            run_cmd(*args)


# -- startup rules ----------------------------------------------------------------------------------
def make_config(**over):
    return Config(_env_file=None, **{**BASE, **over})


DEPLOYED = dict(supabase_url="https://x.supabase.co", storage_provider="supabase", supabase_service_role_key="k")


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_envs_refuse_zero_trusted_proxy_hops(env):
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_HOPS"):
        make_config(env=env, trusted_proxy_hops=0, **DEPLOYED)
    assert make_config(env=env, trusted_proxy_hops=1, **DEPLOYED).trusted_proxy_hops == 1


def test_dev_may_leave_trusted_proxy_hops_at_zero():
    assert make_config(env="dev", trusted_proxy_hops=0).trusted_proxy_hops == 0


def test_resend_backend_needs_an_api_key():
    with pytest.raises(ValidationError, match="RESEND_API_KEY"):
        make_config(email_backend="resend")
    assert make_config(email_backend="resend", resend_api_key="re_x")


def test_production_refuses_the_resend_test_sender_but_staging_keeps_it():
    with pytest.raises(ValidationError, match="test sender"):
        make_config(env="production", email_from="Circuit <onboarding@resend.dev>", **DEPLOYED)
    assert make_config(env="staging", email_from="Circuit <onboarding@resend.dev>", **DEPLOYED)


def test_invites_per_member_defaults_to_three_and_is_bounded():
    assert make_config().invites_per_member == 3
    with pytest.raises(ValidationError):
        make_config(invites_per_member=-1)
