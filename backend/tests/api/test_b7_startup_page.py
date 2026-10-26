"""B7 part 1: the Startup page and the job page in one call each; private counts; under-18 sees verified startups only."""

import pytest

from apps.jobs.models import Application, Job, JobCapability
from apps.matching.models import Capability, MemberSkill
from apps.social.models import MediaUpload, Post, PostMedia
from apps.startups.models import Startup, StartupInterest, StartupMember
from core.storage import get_storage

pytestmark = pytest.mark.django_db


def team_of(make_member, make_startup, **kw):
    founder = make_member("founder", display_name="Priya")
    s = make_startup(claimed_by=founder, **kw)
    StartupMember.objects.create(startup=s, member=founder)
    return founder, s


def add_job(startup, slugs=("seo",), **kw):
    job = Job.objects.create(startup=startup, title=kw.pop("title", "Intern"), is_open=True, **kw)
    for i, slug in enumerate(slugs):
        JobCapability.objects.create(job=job, capability=Capability.objects.get(slug=slug), required=(i == 0))
    return job


def detail(client, startup):
    r = client.get(f"/api/startups/{startup.pk}")
    assert r.status_code == 200, r.content
    return r.json()


# -- private counts -----------------------------------------------------------------------------------
def test_the_team_sees_its_exact_counts(make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup)
    Startup.objects.filter(pk=s.pk).update(view_count=3)
    StartupInterest.objects.create(startup=s, member=make_member("student"))
    body = detail(client_for(founder), s)
    assert body["view_count"] == 3 and body["interest_count"] == 1 and body["is_team"] is True


@pytest.mark.parametrize("role", ["student", "mentor", "investor", "founder"])
def test_nobody_else_sees_a_claimed_startups_counts(make_member, make_startup, client_for, role):
    _, s = team_of(make_member, make_startup)
    Startup.objects.filter(pk=s.pk).update(view_count=40)
    body = detail(client_for(make_member(role)), s)
    assert body["view_count"] is None and body["interest_count"] is None
    assert "40" not in str({k: v for k, v in body.items() if k not in {"id"}})


def test_a_founder_on_an_unclaimed_page_sees_counts_only_from_five(make_member, make_startup, client_for):
    s = make_startup(name="Unclaimed Co", domain="unclaimed.io")
    Startup.objects.filter(pk=s.pk).update(view_count=4)
    for _ in range(4):
        StartupInterest.objects.create(startup=s, member=make_member("student"))
    founder = make_member("founder")
    body = detail(client_for(founder), s)  # this visit makes it 5 views
    assert body["view_count"] == 5 and body["interest_count"] is None  # 4 interested: under the threshold, hidden
    StartupInterest.objects.create(startup=s, member=make_member("student"))
    assert detail(client_for(founder), s)["interest_count"] == 5


def test_students_never_see_an_unclaimed_pages_counts(make_member, make_startup, client_for):
    s = make_startup(domain="u.io")
    Startup.objects.filter(pk=s.pk).update(view_count=99)
    body = detail(client_for(make_member("student")), s)
    assert body["view_count"] is None and body["interest_count"] is None


def test_the_startup_page_needs_sign_in(make_startup, client):
    assert client.get(f"/api/startups/{make_startup().pk}").status_code == 401


# -- founders --------------------------------------------------------------------------------------------
def test_founders_come_with_their_warm_path(make_member, make_startup, connect, client_for):
    founder, s = team_of(make_member, make_startup)
    viewer, friend = make_member("student"), make_member("mentor", display_name="Lakshmi")
    connect(viewer, friend)
    connect(friend, founder)
    f = detail(client_for(viewer), s)["founders"]
    assert [x["person"]["display_name"] for x in f] == ["Priya"]
    assert f[0]["via"]["display_name"] == "Lakshmi" and f[0]["connected"] is False and f[0]["is_me"] is False


def test_a_connected_founder_says_connected_and_a_stranger_has_no_path(make_member, make_startup, connect, client_for):
    founder, s = team_of(make_member, make_startup)
    friend, stranger = make_member("student"), make_member("student")
    connect(friend, founder)
    assert detail(client_for(friend), s)["founders"][0]["connected"] is True
    f = detail(client_for(stranger), s)["founders"][0]
    assert f["connected"] is False and f["via"] is None


def test_the_team_sees_itself_marked(make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup)
    assert detail(client_for(founder), s)["founders"][0]["is_me"] is True


def test_a_founder_with_a_hidden_profile_is_not_listed(make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup)
    founder.profile_visibility = "hidden"
    founder.save()
    assert detail(client_for(make_member("student")), s)["founders"] == []


def test_under_18s_get_no_intro_path(make_member, make_startup, connect, client_for):
    founder, s = team_of(make_member, make_startup)
    kid, friend = make_member("student", is_minor=True), make_member("mentor")
    connect(kid, friend)
    connect(friend, founder)
    f = detail(client_for(kid), s)["founders"][0]
    assert f["via"] is None and f["connected"] is False


# -- build logs ------------------------------------------------------------------------------------------
def post_with_picture(author, visibility, make_image, n=1):
    post = Post.objects.create(author=author, body="Shipped", visibility=visibility)
    for order in range(n):
        up = MediaUpload.objects.create(
            owner=author, purpose="post", path=f"post/{author.pk}/{post.pk}{order}", status="ready", width=64, height=48
        )
        get_storage().put("posts", f"{up.path}/w480.webp", b"x", "image/webp")
        PostMedia.objects.create(post=post, upload=up, alt_text=f"pic {order}", order=order)
    return post


def test_build_logs_show_the_first_picture_of_posts_the_viewer_may_see(make_member, make_startup, make_image, client_for):
    founder, s = team_of(make_member, make_startup)
    public = post_with_picture(founder, "everyone", make_image, n=2)
    post_with_picture(founder, "connections", make_image)  # not for a stranger
    logs = detail(client_for(make_member("student")), s)["build_logs"]
    assert [x["post_id"] for x in logs] == [public.pk]
    assert logs[0]["image"]["alt_text"] == "pic 0" and logs[0]["image"]["w480"].startswith("http")


def test_connections_see_connections_only_logs(make_member, make_startup, make_image, connect, client_for):
    founder, s = team_of(make_member, make_startup)
    friend = make_member("student")
    connect(friend, founder)
    post_with_picture(founder, "connections", make_image)
    assert len(detail(client_for(friend), s)["build_logs"]) == 1


def test_build_logs_are_empty_with_pulse_off(make_member, make_startup, make_image, client_for, settings):
    founder, s = team_of(make_member, make_startup)
    post_with_picture(founder, "everyone", make_image)
    from core import flags

    settings.FEATURES = ",".join(
        f"{n}:{'off' if n == 'pulse' else 'everyone'}" for n in flags.FLAGS if n not in ("promotions", "payments")
    )
    settings.FEATURES += ",promotions:off,payments:off"  # promotions depend on pulse: switch them off with it
    assert detail(client_for(make_member("student")), s)["build_logs"] == []


def test_build_logs_are_capped_at_nine(make_member, make_startup, make_image, client_for):
    founder, s = team_of(make_member, make_startup)
    for _ in range(11):
        post_with_picture(founder, "everyone", make_image)
    assert len(detail(client_for(make_member("student")), s)["build_logs"]) == 9


# -- logo and team size ------------------------------------------------------------------------------------
def upload_logo(client, make_image):
    data = make_image("PNG", (500, 500))
    r = client.post("/api/media/uploads", {"purpose": "startup_logo", "content_type": "image/png", "size": len(data)})
    assert r.status_code == 201, r.content
    up = MediaUpload.objects.get(pk=r.json()["id"])
    get_storage().put("avatars", f"{up.path}/original", data, "image/png")
    client.post(f"/api/media/uploads/{up.pk}/complete")
    return up


def test_the_team_can_set_and_remove_the_logo(make_member, make_startup, make_image, client_for):
    founder, s = team_of(make_member, make_startup)
    c = client_for(founder)
    up = upload_logo(c, make_image)
    body = c.put(f"/api/startups/{s.pk}/logo", {"upload_id": up.pk}).json()
    assert body["logo"].startswith("http")
    other = client_for(make_member("student"))
    assert detail(other, s)["logo"].startswith("http")
    assert other.get("/api/startups/nearby").json()[0]["logo"].startswith("http")
    assert c.delete(f"/api/startups/{s.pk}/logo").json()["logo"] is None
    assert ("avatars", f"{up.path}/w480.webp") not in get_storage().files


def test_replacing_the_logo_deletes_the_old_one(make_member, make_startup, make_image, client_for):
    founder, s = team_of(make_member, make_startup)
    c = client_for(founder)
    first, second = upload_logo(c, make_image), upload_logo(c, make_image)
    c.put(f"/api/startups/{s.pk}/logo", {"upload_id": first.pk})
    c.put(f"/api/startups/{s.pk}/logo", {"upload_id": second.pk})
    assert ("avatars", f"{first.path}/w480.webp") not in get_storage().files


def test_only_the_team_can_change_the_logo(make_member, make_startup, make_image, client_for):
    founder, s = team_of(make_member, make_startup)
    up = upload_logo(client_for(founder), make_image)
    outsider = make_member("founder")  # another founder, not on this team
    assert client_for(outsider).put(f"/api/startups/{s.pk}/logo", {"upload_id": up.pk}).status_code == 403
    assert client_for(outsider).delete(f"/api/startups/{s.pk}/logo").status_code == 403
    assert client_for(founder).put(f"/api/startups/{s.pk}/logo", {"upload_id": 999999}).status_code == 404


def test_the_team_sets_the_team_size(make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup)
    r = client_for(founder).patch(f"/api/startups/{s.pk}", {"team_size": 7})
    assert r.status_code == 200 and r.json()["team_size"] == 7
    assert client_for(founder).patch(f"/api/startups/{s.pk}", {"team_size": 0}).status_code == 422
    assert client_for(make_member("founder")).patch(f"/api/startups/{s.pk}", {"team_size": 9}).status_code == 403


# -- under 18: verified startups only --------------------------------------------------------------------
@pytest.fixture
def two_startups(lists, make_member, make_startup):
    founder, verified = team_of(make_member, make_startup, name="Verified Co", domain="verified.io", hiring=True)
    unverified = make_startup(name="Unverified Co", domain="unverified.io", hiring=True)
    return add_job(verified, title="Verified role"), add_job(unverified, title="Unverified role")


def test_an_under_18_only_sees_roles_at_verified_startups(two_startups, make_member, client_for):
    ok, hidden = two_startups
    c = client_for(make_member("student", is_minor=True))
    assert [j["title"] for j in c.get("/api/jobs").json()["items"]] == ["Verified role"]
    assert c.get(f"/api/jobs/{ok.pk}").status_code == 200
    assert c.get(f"/api/jobs/{hidden.pk}").status_code == 404
    adult = client_for(make_member("student"))
    assert len(adult.get("/api/jobs").json()["items"]) == 2 and adult.get(f"/api/jobs/{hidden.pk}").status_code == 200


def test_an_under_18_cannot_apply_to_an_unverified_startup(two_startups, make_member, client_for):
    ok, hidden = two_startups
    c = client_for(make_member("student", is_minor=True))
    assert c.post(f"/api/jobs/{hidden.pk}/apply").status_code == 404
    assert not Application.objects.exists()
    assert c.post(f"/api/jobs/{ok.pk}/apply").status_code == 201


def test_an_unverified_startup_looks_like_it_has_no_roles_to_an_under_18(two_startups, make_member, client_for):
    ok, hidden = two_startups
    c = client_for(make_member("student", is_minor=True))
    pins = {p["name"]: p for p in c.get("/api/startups/nearby?lat=13.0827&lng=80.2707").json()}
    assert pins["Verified Co"]["hiring"] is True and pins["Verified Co"]["open_roles"] == 1
    assert pins["Unverified Co"]["hiring"] is False and pins["Unverified Co"]["open_roles"] == 0
    body = c.get(f"/api/startups/{hidden.startup_id}").json()
    assert body["hiring"] is False and body["open_jobs"] == [] and body["match_pct"] is None
    assert c.get(f"/api/startups/{ok.startup_id}").json()["open_jobs"][0]["title"] == "Verified role"


def test_the_hiring_filter_never_returns_unverified_startups_to_an_under_18(two_startups, make_member, client_for):
    c = client_for(make_member("student", is_minor=True))
    names = [p["name"] for p in c.get("/api/startups/nearby?lat=13.0827&lng=80.2707&hiring=true").json()]
    assert names == ["Verified Co"]
    names = [p["name"] for p in c.get("/api/startups/nearby?lat=13.0827&lng=80.2707&capability=seo").json()]
    assert names == ["Verified Co"]


def test_pulse_and_live_wire_leave_out_unverified_roles_for_an_under_18(two_startups, make_member, client_for, settings):
    kid = make_member("student", is_minor=True)
    for ep in ("/api/pulse", "/api/livewire"):
        assert "Unverified role" not in client_for(kid).get(ep).content.decode()


def test_skills_in_demand_for_an_under_18_counts_verified_roles_only(two_startups, make_member, client_for):
    kid, adult = client_for(make_member("student", is_minor=True)), client_for(make_member("student"))
    assert kid.get("/api/jobs/skills-in-demand").json() == [{"slug": "seo", "name": "SEO", "open_roles": 1}]
    assert adult.get("/api/jobs/skills-in-demand").json()[0]["open_roles"] == 2


# -- the job page ------------------------------------------------------------------------------------------
def test_the_job_page_carries_everything_in_one_call(lists, make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup, name="Aravind Pathology")
    job = add_job(s, duration_weeks=12, starts_on="2026-12-01")
    student = make_member("student")
    MemberSkill.objects.create(member=student, capability=Capability.objects.get(slug="seo"), level=2)
    body = client_for(student).get(f"/api/jobs/{job.pk}").json()
    assert body["startup_verified"] is True and body["duration_weeks"] == 12 and body["starts_on"] == "2026-12-01"
    assert body["contact"]["display_name"] == "Priya" and body["is_team"] is False
    assert client_for(founder).get(f"/api/jobs/{job.pk}").json()["is_team"] is True


def test_an_unclaimed_startups_role_has_no_contact(lists, make_member, make_startup, client_for):
    job = add_job(make_startup(domain="no.io"))
    body = client_for(make_member("student")).get(f"/api/jobs/{job.pk}").json()
    assert body["contact"] is None and body["startup_verified"] is False and body["is_team"] is False


def test_founders_can_post_a_role_with_a_duration_and_start(lists, make_member, make_startup, client_for):
    founder, s = team_of(make_member, make_startup)
    r = client_for(founder).post(
        "/api/jobs",
        {"startup_id": s.pk, "title": "Design intern", "capabilities": [{"capability": "seo"}], "duration_weeks": 8,
         "starts_on": "2027-01-10"},
    )  # fmt: skip
    assert r.status_code == 200 and r.json()["duration_weeks"] == 8 and r.json()["starts_on"] == "2027-01-10"
    bad = client_for(founder).post(
        "/api/jobs", {"startup_id": s.pk, "title": "Design intern", "capabilities": [{"capability": "seo"}], "duration_weeks": 0}
    )
    assert bad.status_code == 422


# -- applicants: skill names, one query for all the skills --------------------------------------------------
def test_applicants_come_with_skill_names_in_a_fixed_number_of_queries(
    lists, make_member, make_startup, client_for, django_assert_max_num_queries
):
    founder, s = team_of(make_member, make_startup)
    job = add_job(s)
    cap = Capability.objects.get(slug="seo")
    for _ in range(12):
        st = make_member("student")
        MemberSkill.objects.create(member=st, capability=cap, level=3, proof_url="https://example.com/p")
        Application.objects.create(job=job, student=st, skill_match=0.5)
    c = client_for(founder)
    c.get(f"/api/jobs/{job.pk}/applicants")
    with django_assert_max_num_queries(12):
        r = c.get(f"/api/jobs/{job.pk}/applicants?limit=12")
    skill = r.json()["items"][0]["skills"][0]
    assert skill == {"capability": "seo", "name": cap.name, "level": 3, "proof_url": "https://example.com/p"}
