"""Demo story 3: a tier-3-college student is matched on skills to a nearby hiring startup, applies, and tops the applicants."""

import pytest

from apps.jobs.models import Job
from tests.demo.conftest import person

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.story(3)]


def test_story_3_ravi_finds_applies_and_is_the_top_applicant(seeded, client_for):
    ravi, divya = person("ravi"), person("divya")
    job = Job.objects.get(title="Frontend Intern", startup__name="Pixelwave Labs")
    rc = client_for(ravi)

    listed = rc.get("/api/jobs?max_distance_km=25&limit=100").json()["items"]
    mine = next(j for j in listed if j["id"] == job.pk)
    assert mine["skill_match"] >= 0.9 and mine["distance_km"] < 25 and mine["applied"] is False
    assert [j["id"] for j in listed].index(job.pk) < 3, "the matching job should be near the top of Ravi's list"

    page = rc.get(f"/api/jobs/{job.pk}").json()
    assert {c["slug"]: c["your_level"] for c in page["capabilities"]}["frontend-dev"] == 3

    r = rc.post(f"/api/jobs/{job.pk}/apply")
    assert r.status_code == 201 and r.json()["status"] == "applied"

    applicants = client_for(divya).get(f"/api/jobs/{job.pk}/applicants").json()["items"]
    assert len(applicants) >= 3, "there should be weaker rival applicants"
    top = applicants[0]
    assert top["student_id"] == ravi.pk and top["skill_match"] > applicants[1]["skill_match"]
    assert "college" not in top and any(s["proof_url"] for s in top["skills"])  # ranked on skills and proof of work


def test_story_3_the_founder_is_told_and_can_shortlist(seeded, client_for):
    ravi, divya = person("ravi"), person("divya")
    job = Job.objects.get(title="Frontend Intern")
    client_for(ravi).post(f"/api/jobs/{job.pk}/apply")
    app_id = client_for(divya).get(f"/api/jobs/{job.pk}/applicants").json()["items"][0]["application_id"]
    assert client_for(divya).patch(f"/api/applications/{app_id}", {"status": "shortlisted"}).json()["status"] == "shortlisted"
    kinds = [n["kind"] for n in client_for(ravi).get("/api/notifications").json()["items"]]
    assert "application.status" in kinds
    assert "application.received" in [n["kind"] for n in client_for(divya).get("/api/notifications").json()["items"]]
