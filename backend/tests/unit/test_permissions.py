import pytest

from apps.accounts.models import Member
from core.errors import Forbidden
from core.permissions import in_org, require_level, require_org_admin, require_role

pytestmark = pytest.mark.django_db


def test_require_role(make_member):
    require_role(make_member("founder"), "founder", "mentor")
    with pytest.raises(Forbidden):
        require_role(make_member("student"), "founder", "mentor")


def test_super_admin_has_no_implicit_bypass(make_member):
    with pytest.raises(Forbidden):
        require_role(make_member("super_admin"), "founder")


def test_require_level(make_member):
    require_level(make_member(level=2), 2)
    with pytest.raises(Forbidden):
        require_level(make_member(level=1), 2)


def test_require_org_admin(make_member, make_org):
    org = make_org()
    assert require_org_admin(make_member("partner_admin", org=org)) == org.pk
    with pytest.raises(Forbidden):
        require_org_admin(make_member("partner_admin", org=None))  # an admin of nothing
    with pytest.raises(Forbidden):
        require_org_admin(make_member("student", org=org))  # right org, wrong role
    with pytest.raises(Forbidden):
        require_org_admin(make_member("super_admin", org=org))


def test_in_org_scopes_queryset(make_member, make_org):
    a, b = make_org("A"), make_org("B")
    mine, theirs = make_member(org=a), make_member(org=b)
    viewer = make_member("partner_admin", org=a)
    ids = set(in_org(Member.objects.all(), viewer).values_list("pk", flat=True))
    assert mine.pk in ids and theirs.pk not in ids


def test_in_org_without_organisation_sees_nothing(make_member, make_org):
    make_member(org=make_org())
    assert in_org(Member.objects.all(), make_member(org=None)).count() == 0
