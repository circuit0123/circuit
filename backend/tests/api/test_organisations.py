import pytest

from apps.accounts.admin import MemberForm
from apps.accounts.models import Member
from apps.events.models import Event
from apps.organisations import services
from apps.organisations.admin import OrganisationForm
from apps.organisations.models import Organisation
from core.errors import Forbidden

pytestmark = pytest.mark.django_db


# --- join by code --------------------------------------------------------------------------------


def test_join_by_code(make_member, make_org, client_for):
    org = make_org("KIT", code="ABCDE12345")
    m = make_member()
    r = client_for(m).post("/api/organisations/join", {"code": " abcde12345 "})
    assert r.status_code == 200 and r.json()["name"] == "KIT" and r.json()["join_code"] is None
    m.refresh_from_db()
    assert m.organisation_id == org.pk
    e = Event.objects.get(type="org.joined")
    assert e.actor_id == m.pk and e.payload == {"method": "code"} and e.target_id == org.pk


def test_join_with_bad_code_404(make_member, client_for):
    r = client_for(make_member()).post("/api/organisations/join", {"code": "NOPE"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_join_when_already_in_org_409(make_member, make_org, client_for):
    a = make_org("A", code="AAAAAAAAAA")
    make_org("B", code="BBBBBBBBBB")
    m = make_member(org=a)
    r = client_for(m).post("/api/organisations/join", {"code": "BBBBBBBBBB"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_in_organisation"
    m.refresh_from_db()
    assert m.organisation_id == a.pk


def test_join_code_guessing_is_rate_limited(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "org_join": (3, 60)}
    c = client_for(make_member())
    codes = [c.post("/api/organisations/join", {"code": f"WRONG{i}"}).status_code for i in range(5)]
    assert codes == [404, 404, 404, 429, 429]


def test_rate_limit_is_per_member(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "org_join": (1, 60)}
    assert client_for(make_member()).post("/api/organisations/join", {"code": "X"}).status_code == 404
    assert client_for(make_member()).post("/api/organisations/join", {"code": "X"}).status_code == 404


# --- join by verified email domain ---------------------------------------------------------------


def test_join_by_verified_email(make_member, make_org, client_for):
    org = make_org(domains=["kit.edu.in"])
    m = make_member()
    r = client_for(m, email="Asha@KIT.edu.in").post("/api/organisations/join-by-email")
    assert r.status_code == 200 and r.json()["id"] == org.pk
    assert Event.objects.get(type="org.joined").payload == {"method": "email_domain"}


def test_email_in_request_body_is_ignored(make_member, make_org, client_for):
    make_org(domains=["kit.edu.in"])
    m = make_member()
    r = client_for(m, email="me@example.org").post("/api/organisations/join-by-email", {"email": "x@kit.edu.in"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_matching_organisation"
    m.refresh_from_db()
    assert m.organisation_id is None


def test_lookalike_domains_do_not_match(make_member, make_org, client_for):
    make_org(domains=["kit.edu.in"])
    for email in ["a@evilkit.edu.in", "a@kit.edu.in.evil.com", "a@sub.kit.edu.in"]:
        assert client_for(make_member(), email=email).post("/api/organisations/join-by-email").status_code == 404


def test_unverified_provider_cannot_join_by_email(make_member, make_org, client_for):
    make_org(domains=["kit.edu.in"])
    r = client_for(make_member(), email="a@kit.edu.in", app_metadata={"provider": "phone"}).post(
        "/api/organisations/join-by-email"
    )
    assert r.status_code == 404


# --- mine / leave --------------------------------------------------------------------------------


def test_mine_404_without_org(make_member, client_for):
    assert client_for(make_member()).get("/api/organisations/mine").status_code == 404


def test_join_code_only_visible_to_own_partner_admin(make_member, make_org, client_for):
    org, other = make_org("A", code="AAAAAAAAAA"), make_org("B", code="BBBBBBBBBB")
    assert client_for(make_member("partner_admin", org=org)).get("/api/organisations/mine").json()["join_code"] == "AAAAAAAAAA"
    assert client_for(make_member("student", org=org)).get("/api/organisations/mine").json()["join_code"] is None
    # an admin of org B never sees org A's data through /mine
    assert client_for(make_member("partner_admin", org=other)).get("/api/organisations/mine").json()["id"] == other.pk


def test_leave(make_member, make_org, client_for):
    m = make_member(org=make_org(), visible_to_org=True)
    assert client_for(m).post("/api/organisations/leave").status_code == 204
    m.refresh_from_db()
    assert m.organisation_id is None and m.visible_to_org is False
    assert Event.objects.filter(type="org.left", actor_id=m.pk).exists()


def test_leave_without_org_409(make_member, client_for):
    assert client_for(make_member()).post("/api/organisations/leave").status_code == 409


def test_partner_admin_cannot_leave(make_member, make_org, client_for):
    admin = make_member("partner_admin", org=make_org())
    assert client_for(admin).post("/api/organisations/leave").status_code == 403


# --- partner admin: list and remove (org scoping + IDOR) -----------------------------------------


def test_members_list_is_scoped_and_opt_in_only(make_member, make_org, client_for):
    a, b = make_org("A"), make_org("B")
    admin = make_member("partner_admin", org=a)
    visible = make_member(org=a, visible_to_org=True)
    make_member(org=a, visible_to_org=False)  # did not opt in
    make_member(org=b, visible_to_org=True)  # someone else's organisation
    make_member(org=None, visible_to_org=True)
    body = client_for(admin).get("/api/organisations/mine/members").json()
    assert [i["id"] for i in body["items"]] == [visible.pk] and body["count"] == 1 and body["next_offset"] is None
    assert set(body["items"][0]) == {"id", "display_name", "role", "college", "verification_level"}  # no bio/location/etc.


def test_members_list_paginates(make_member, make_org, client_for):
    org = make_org()
    admin = make_member("partner_admin", org=org)
    for _ in range(5):
        make_member(org=org, visible_to_org=True)
    body = client_for(admin).get("/api/organisations/mine/members?limit=2&offset=0").json()
    assert len(body["items"]) == 2 and body["count"] == 5 and body["next_offset"] == 2


def test_members_list_rejects_bad_params(make_member, make_org, client_for):
    admin = make_member("partner_admin", org=make_org())
    r = client_for(admin).get("/api/organisations/mine/members?limit=1000")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_remove_member(make_member, make_org, client_for):
    org = make_org()
    admin, target = make_member("partner_admin", org=org), make_member(org=org, visible_to_org=True)
    assert client_for(admin).delete(f"/api/organisations/mine/members/{target.pk}").status_code == 204
    target.refresh_from_db()
    assert target.organisation_id is None and target.visible_to_org is False
    e = Event.objects.get(type="org.member_removed")
    assert e.actor_id == admin.pk and e.payload == {"removed_member_id": target.pk}


def test_idor_cannot_remove_member_of_another_org(make_member, make_org, client_for):
    a, b = make_org("A"), make_org("B")
    admin_a, victim = make_member("partner_admin", org=a), make_member(org=b)
    r = client_for(admin_a).delete(f"/api/organisations/mine/members/{victim.pk}")
    assert r.status_code == 404  # same answer as a nonexistent id: no existence leak
    victim.refresh_from_db()
    assert victim.organisation_id == b.pk


def test_idor_cannot_remove_member_with_no_org(make_member, make_org, client_for):
    admin, loner = make_member("partner_admin", org=make_org()), make_member()
    assert client_for(admin).delete(f"/api/organisations/mine/members/{loner.pk}").status_code == 404


def test_cannot_remove_self_or_other_partner_admin(make_member, make_org, client_for):
    org = make_org()
    admin, peer = make_member("partner_admin", org=org), make_member("partner_admin", org=org)
    c = client_for(admin)
    assert c.delete(f"/api/organisations/mine/members/{admin.pk}").status_code == 403
    assert c.delete(f"/api/organisations/mine/members/{peer.pk}").status_code == 403


def test_non_admin_cannot_list_or_remove(make_member, make_org, client_for):
    org = make_org()
    student, other = make_member("student", org=org), make_member(org=org)
    c = client_for(student)
    assert c.get("/api/organisations/mine/members").status_code == 403
    assert c.delete(f"/api/organisations/mine/members/{other.pk}").status_code == 403
    other.refresh_from_db()
    assert other.organisation_id == org.pk


def test_demoted_admin_without_org_is_denied(make_member, client_for):
    ghost_admin = make_member("partner_admin", org=None)
    assert client_for(ghost_admin).get("/api/organisations/mine/members").status_code == 403


# --- services / admin forms ----------------------------------------------------------------------


def test_join_codes_are_unambiguous_and_unique():
    codes = {services.generate_join_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(len(c) == 10 and not set(c) & set("01OIL") for c in codes)


def test_clean_domains(make_org):
    assert services.clean_domains([" KIT.edu.in ", "@kit.edu.in", "cs.kit.edu.in"]) == ["kit.edu.in", "cs.kit.edu.in"]
    for bad in ["gmail.com", "nodot", "a b.com", "x@y.com", ""]:
        with pytest.raises(ValueError):
            services.clean_domains([bad])
    org = make_org(domains=["kit.edu.in"])
    with pytest.raises(ValueError):
        services.clean_domains(["kit.edu.in"])  # already owned by another organisation
    assert services.clean_domains(["kit.edu.in"], exclude_org_id=org.pk) == ["kit.edu.in"]


def test_admin_form_rejects_public_domain_and_generates_code(make_org):
    form = OrganisationForm(data={"name": "X", "kind": "college", "city": "Chennai", "email_domains": "gmail.com"})
    assert not form.is_valid() and "email_domains" in form.errors
    form = OrganisationForm(data={"name": "X", "kind": "college", "city": "Chennai", "email_domains": "x.edu.in, Y.edu.in"})
    assert form.is_valid() and form.cleaned_data["email_domains"] == ["x.edu.in", "y.edu.in"]


def test_admin_organisation_save_generates_join_code_and_audits(rf):
    from django.contrib import admin
    from django.contrib.auth import get_user_model

    from apps.moderation.models import AuditLog

    staff = get_user_model().objects.create_superuser("root", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    obj = Organisation(name="N", kind="college", city="C")
    admin.site._registry[Organisation].save_model(request, obj, form=type("F", (), {"changed_data": ["name"]})(), change=False)
    obj.refresh_from_db()
    assert len(obj.join_code) == 10
    assert AuditLog.objects.filter(actor=staff, action="create", target_type="organisations.organisation").exists()


def test_partner_admin_requires_an_organisation_in_admin_form(make_member, make_org):
    m = make_member()
    assert not MemberForm(data={"role": "partner_admin", "verification_level": 1, "organisation": ""}, instance=m).is_valid()
    org = make_org()
    assert MemberForm(data={"role": "partner_admin", "verification_level": 1, "organisation": org.pk}, instance=m).is_valid()


def test_nothing_is_written_for_failed_actions(make_member, client_for):
    client_for(make_member()).post("/api/organisations/join", {"code": "NOPE"})
    assert not Event.objects.filter(type="org.joined").exists()
    assert Member.objects.count() == 1


def test_remove_member_service_refuses_admin_without_org(make_member):
    loner = make_member()
    ghost_admin = make_member("partner_admin", org=None)
    with pytest.raises(Forbidden):
        services.remove_member(ghost_admin, loner.pk)  # would match IS NULL if unguarded
    loner.refresh_from_db()
    assert Event.objects.filter(type="org.member_removed").count() == 0
