import pytest

from apps.events.models import Event
from apps.jobs.models import Application, Job, JobCapability
from apps.matching.models import Capability, MemberSkill
from apps.notifications.models import Notification
from apps.startups.models import Startup, StartupMember

pytestmark = pytest.mark.django_db


@pytest.fixture
def team(lists, make_member, make_startup):
    """A claimed startup with its founder on the team."""
    founder = make_member("founder")
    startup = make_startup("Acme", "acme.io", claimed_by=founder)
    StartupMember.objects.create(startup=startup, member=founder, role="founder")
    return founder, startup


def skill(member, slug, level=3):
    return MemberSkill.objects.create(member=member, capability=Capability.objects.get(slug=slug), level=level)


def add_job(startup, caps, **kw):
    job = Job.objects.create(startup=startup, title=kw.pop("title", "Intern"), **kw)
    for i, slug in enumerate(caps):
        JobCapability.objects.create(job=job, capability=Capability.objects.get(slug=slug), required=(i == 0))
    return job


def post_job(client, startup, **over):
    body = {"startup_id": startup.pk, "title": "Frontend intern", "capabilities": [{"capability": "frontend-dev"}], **over}
    return client.post("/api/jobs", body)


# -- listing and job page -----------------------------------------------------------------
def test_student_list_is_ranked_by_skill_match(team, make_member, client_for):
    _, startup = team
    weak = add_job(startup, ["seo"], title="SEO")
    strong = add_job(startup, ["frontend-dev"], title="Frontend")
    student = make_member("student")
    skill(student, "frontend-dev")
    rows = client_for(student).get("/api/jobs").json()["items"]
    assert [r["id"] for r in rows] == [strong.pk, weak.pk]
    assert rows[0]["skill_match"] > rows[1]["skill_match"] and rows[0]["applied"] is False


def test_non_student_list_has_no_match_and_hides_closed(team, make_member, client_for):
    _, startup = team
    open_job = add_job(startup, ["seo"])
    add_job(startup, ["seo"], is_open=False)
    rows = client_for(make_member("mentor")).get("/api/jobs").json()["items"]
    assert [r["id"] for r in rows] == [open_job.pk]
    assert rows[0]["skill_match"] is None and rows[0]["applied"] is None


def test_list_filters(team, make_member, client_for):
    _, startup = team
    a = add_job(startup, ["seo"], kind="internship", stipend_max=8000)
    b = add_job(startup, ["frontend-dev"], kind="full_time", stipend_max=40000)
    c = client_for(make_member("student"))
    ids = lambda q: [r["id"] for r in c.get("/api/jobs" + q).json()["items"]]  # noqa: E731
    assert ids("?kind=full_time") == [b.pk]
    assert ids("?capability=seo") == [a.pk]
    assert ids("?min_stipend=20000") == [b.pk]
    assert ids(f"?startup_id={startup.pk}") and set(ids(f"?startup_id={startup.pk}")) == {a.pk, b.pk}
    assert c.get("/api/jobs?kind=nonsense").status_code == 422


def test_job_page_shows_my_level_per_skill(team, make_member, client_for):
    _, startup = team
    job = add_job(startup, ["frontend-dev", "seo"])
    student = make_member("student")
    skill(student, "frontend-dev", 3)
    body = client_for(student).get(f"/api/jobs/{job.pk}").json()
    levels = {c["slug"]: c["your_level"] for c in body["capabilities"]}
    assert levels == {"frontend-dev": 3, "seo": None}


def test_closed_job_visible_to_its_team_only(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["seo"], is_open=False)
    assert client_for(make_member("student")).get(f"/api/jobs/{job.pk}").status_code == 404
    assert client_for(founder).get(f"/api/jobs/{job.pk}").status_code == 200


# -- posting -------------------------------------------------------------------------------
def test_team_posts_job_and_startup_becomes_hiring(team, client_for):
    founder, startup = team
    r = post_job(client_for(founder), startup, stipend_min=5000, stipend_max=9000)
    assert r.status_code == 200, r.content
    startup.refresh_from_db()
    assert startup.hiring is True
    assert Event.objects.filter(type="job.created", target_id=r.json()["id"]).exists()


def test_posting_failures(team, make_member, make_startup, client_for):
    founder, startup = team
    c = client_for(founder)
    assert post_job(c, startup, capabilities=[{"capability": "not-a-skill"}]).status_code == 422
    assert post_job(c, startup, stipend_min=9000, stipend_max=5000).status_code == 422
    assert post_job(c, startup, capabilities=[]).status_code == 422
    other = make_startup("Other", "other.io", claimed_by=make_member("founder"))
    assert post_job(c, other).status_code == 403  # a real startup that is not mine
    assert post_job(client_for(make_member("student")), startup).status_code == 403


def test_unclaimed_startup_cannot_post(lists, make_member, make_startup, client_for):
    founder = make_member("founder")
    startup = make_startup("Unclaimed", "unclaimed.io")
    StartupMember.objects.create(startup=startup, member=founder, role="founder")
    assert post_job(client_for(founder), startup).status_code == 403


def test_edit_and_close_job_updates_hiring_and_rescores(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["seo"])
    student = make_member("student")
    skill(student, "frontend-dev")
    sc = client_for(student)
    assert sc.post(f"/api/jobs/{job.pk}/apply").status_code == 201
    assert Application.objects.get(student=student).skill_match == 0

    fc = client_for(founder)
    r = fc.patch(f"/api/jobs/{job.pk}", {"capabilities": [{"capability": "frontend-dev"}]})
    assert r.status_code == 200, r.content
    assert Application.objects.get(student=student).skill_match > 0  # re-scored against the new requirements

    assert fc.patch(f"/api/jobs/{job.pk}", {"is_open": False}).status_code == 200
    startup.refresh_from_db()
    assert startup.hiring is False  # no open roles left
    assert fc.patch(f"/api/jobs/{job.pk}", {"stipend_min": 9, "stipend_max": 1}).status_code == 422


def test_edit_job_of_another_startup_is_403(team, make_member, make_startup, client_for):
    _, startup = team
    job = add_job(startup, ["seo"])
    stranger = make_member("founder")
    make_startup("Theirs", "theirs.io", claimed_by=stranger)
    assert client_for(stranger).patch(f"/api/jobs/{job.pk}", {"title": "Hijacked"}).status_code == 403
    job.refresh_from_db()
    assert job.title == "Intern"


# -- applying -------------------------------------------------------------------------------
def test_apply_is_one_click_idempotent_and_notifies_team(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["frontend-dev"])
    student = make_member("student")
    skill(student, "frontend-dev")
    c = client_for(student)
    first = c.post(f"/api/jobs/{job.pk}/apply")
    again = c.post(f"/api/jobs/{job.pk}/apply")
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"] and first.json()["skill_match"] > 0
    assert Application.objects.filter(job=job, student=student).count() == 1
    assert Notification.objects.filter(member=founder, kind="application.received").count() == 1  # not twice
    assert Event.objects.filter(type="application.created", actor_id=student.pk).count() == 1
    assert [a["job_id"] for a in c.get("/api/me/applications").json()["items"]] == [job.pk]
    assert c.get(f"/api/jobs/{job.pk}").json()["applied"] is True


def test_apply_to_closed_or_missing_job(team, make_member, client_for):
    _, startup = team
    job = add_job(startup, ["seo"], is_open=False)
    c = client_for(make_member("student"))
    assert c.post(f"/api/jobs/{job.pk}/apply").status_code == 409
    assert c.post("/api/jobs/999999/apply").status_code == 404


def test_apply_is_rate_limited(team, make_member, client_for, settings):
    _, startup = team
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "application": (2, 86400)}
    c = client_for(make_member("student"))
    codes = [c.post(f"/api/jobs/{add_job(startup, ['seo']).pk}/apply").status_code for _ in range(3)]
    assert codes[:2] == [201, 201] and codes[2] == 429


def test_withdraw_then_reapply(team, make_member, client_for):
    _, startup = team
    job = add_job(startup, ["seo"])
    student = make_member("student")
    c = client_for(student)
    app_id = c.post(f"/api/jobs/{job.pk}/apply").json()["id"]
    assert c.post(f"/api/applications/{app_id}/withdraw").json()["status"] == "withdrawn"
    assert c.post(f"/api/applications/{app_id}/withdraw").status_code == 200  # safe to repeat
    r = c.post(f"/api/jobs/{job.pk}/apply")
    assert r.status_code == 201 and r.json()["id"] == app_id and r.json()["status"] == "applied"


def test_cannot_withdraw_someone_elses_or_a_decided_application(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["seo"])
    a, b = make_member("student"), make_member("student")
    app_id = client_for(a).post(f"/api/jobs/{job.pk}/apply").json()["id"]
    assert client_for(b).post(f"/api/applications/{app_id}/withdraw").status_code == 404
    client_for(founder).patch(f"/api/applications/{app_id}", {"status": "rejected"})
    assert client_for(a).post(f"/api/applications/{app_id}/withdraw").status_code == 409


# -- founder view ----------------------------------------------------------------------------
def test_applicants_ranked_by_skill_match_not_college(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["frontend-dev", "seo"])
    tier1 = make_member("student", college="Famous Institute of Technology")
    tier3 = make_member("student", college="Small Town Polytechnic")
    skill(tier3, "frontend-dev", 3)
    skill(tier3, "seo", 2)
    for s in (tier1, tier3):  # the famous college applies first
        client_for(s).post(f"/api/jobs/{job.pk}/apply")
    rows = client_for(founder).get(f"/api/jobs/{job.pk}/applicants").json()["items"]
    assert [r["student_id"] for r in rows] == [tier3.pk, tier1.pk]
    assert "college" not in rows[0] and {s["capability"] for s in rows[0]["skills"]} == {"frontend-dev", "seo"}


def test_applicants_hide_withdrawn_and_are_team_only(team, make_member, make_startup, client_for):
    founder, startup = team
    job = add_job(startup, ["seo"])
    student = make_member("student")
    sc = client_for(student)
    sc.post(f"/api/applications/{sc.post(f'/api/jobs/{job.pk}/apply').json()['id']}/withdraw")
    assert client_for(founder).get(f"/api/jobs/{job.pk}/applicants").json()["items"] == []
    stranger = make_member("founder")
    make_startup("Theirs", "theirs.io", claimed_by=stranger)
    assert client_for(stranger).get(f"/api/jobs/{job.pk}/applicants").status_code == 403


def test_status_flow_notifies_student(team, make_member, client_for):
    founder, startup = team
    job = add_job(startup, ["seo"])
    student = make_member("student")
    app_id = client_for(student).post(f"/api/jobs/{job.pk}/apply").json()["id"]
    fc = client_for(founder)
    assert fc.patch(f"/api/applications/{app_id}", {"status": "hired"}).status_code == 409  # must shortlist first
    assert fc.patch(f"/api/applications/{app_id}", {"status": "shortlisted"}).json()["status"] == "shortlisted"
    assert fc.patch(f"/api/applications/{app_id}", {"status": "hired"}).json()["status"] == "hired"
    assert fc.patch(f"/api/applications/{app_id}", {"status": "rejected"}).status_code == 409  # final
    assert fc.patch(f"/api/applications/{app_id}", {"status": "applied"}).status_code == 422
    kinds = list(Notification.objects.filter(member=student).values_list("payload__status", flat=True))
    assert kinds == ["shortlisted", "hired"]
    assert Event.objects.filter(type="application.status_changed").count() == 2


def test_status_change_on_another_startups_application_is_404(team, make_member, make_startup, client_for):
    _, startup = team
    job = add_job(startup, ["seo"])
    app_id = client_for(make_member("student")).post(f"/api/jobs/{job.pk}/apply").json()["id"]
    stranger = make_member("founder")
    make_startup("Theirs", "theirs.io", claimed_by=stranger)
    StartupMember.objects.create(startup=Startup.objects.get(website_domain="theirs.io"), member=stranger, role="founder")
    assert client_for(stranger).patch(f"/api/applications/{app_id}", {"status": "shortlisted"}).status_code == 404
    assert Application.objects.get(pk=app_id).status == "applied"
