"""F7: verification levels 1-3 are shown as badges wherever one person is shown to another, and level 3 is admin-only."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage

from apps.accounts.admin import MemberForm
from apps.accounts.models import Connection, Member
from apps.matching import services as matching
from apps.matching.models import Capability, Need, Offer
from apps.moderation.models import AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def verified(lists, make_member):
    """A level-3 mentor who offers what a founder needs, and is connected to a second founder."""
    mentor = make_member("mentor", level=3)
    founder = make_member("founder")
    Need.objects.create(member=founder, capability=Capability.objects.get(slug="seo"), description="")
    Offer.objects.create(member=mentor, capability=Capability.objects.get(slug="seo"), description="")
    return mentor, founder


def test_level_is_on_my_own_profile_and_on_public_profiles(verified, client_for):
    mentor, founder = verified
    assert client_for(mentor).get("/api/me").json()["verification_level"] == 3
    assert client_for(founder).get(f"/api/members/{mentor.pk}").json()["verification_level"] == 3


def test_level_is_on_matches(verified, client_for):
    mentor, founder = verified
    matching.compute_all()
    row = client_for(founder).get("/api/matches").json()["items"][0]
    assert row["candidate_id"] == mentor.pk and row["verification_level"] == 3


def test_level_is_on_intros(verified, make_member, client_for):
    mentor, founder = verified
    third = make_member("investor")
    Connection.objects.create(member_a_id=min(founder.pk, mentor.pk), member_b_id=max(founder.pk, mentor.pk))
    Connection.objects.create(member_a_id=min(third.pk, mentor.pk), member_b_id=max(third.pk, mentor.pk))
    path = client_for(founder).get(f"/api/intros/path/{third.pk}").json()
    assert path["via"]["verification_level"] == 3 and path["target"]["verification_level"] == 1


def test_a_new_member_starts_at_level_1_and_cannot_set_their_own_level(make_member, client_for):
    m = make_member("student")
    assert m.verification_level == 1
    r = client_for(m).patch("/api/me", {"verification_level": 3, "role": "super_admin"})
    m.refresh_from_db()
    assert m.verification_level == 1 and m.role == "student" and r.status_code in (200, 422)


def test_level_3_is_set_by_a_super_admin_in_django_admin_and_audited(rf, make_member):
    m = make_member("mentor")
    staff = get_user_model().objects.create_superuser("verifier", password="a-long-test-password-1")
    request = rf.post("/")
    request.user, request._messages = staff, CookieStorage(rf.post("/"))
    form = MemberForm(data={"role": "mentor", "verification_level": 3, "organisation": ""}, instance=m)
    assert form.is_valid()
    admin.site._registry[Member].save_model(request, m, form, change=True)
    m.refresh_from_db()
    assert m.verification_level == 3
    entry = AuditLog.objects.get(actor=staff, action="update", target_id=str(m.pk))
    assert "verification_level" in entry.payload["fields"]
