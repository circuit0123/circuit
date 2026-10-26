"""A sweep over every committed fixture (every response the frontend will ever be shown) for things that must never be sent."""

import json
import re

from tests.contract import runner

NEVER = {"phone", "score", "components", "embedding", "password", "secret", "followers", "follower_count", "connection_count"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
COMPANY_CONTACTS = ("support.grievance.email", "support_email", "grievance.email")  # Circuit's own published addresses


def responses():
    for f in sorted(runner.FIXTURES.glob("*/*.json")):
        doc = json.loads(f.read_text())
        for call in doc["calls"]:
            yield f"{doc['screen']}/{doc['scenario']}", doc, call


def walk(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield f"{path}.{k}", k, v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")


def test_no_response_ever_carries_a_forbidden_field():
    found = [
        f"{name} {call['request']['path']}{p}"
        for name, _, call in responses()
        if call["status"] < 400
        for p, key, _ in walk(call["response"])
        if key in NEVER
    ]
    assert not found, f"fields that must never be sent: {found}"


def test_no_response_contains_an_email_address_except_circuits_own_contact_details():
    found = [
        f"{name} {call['request']['path']}{p}"
        for name, _, call in responses()
        if call["status"] < 400
        for p, _, value in walk(call["response"])
        if isinstance(value, str) and EMAIL.search(value) and not p.endswith(COMPANY_CONTACTS)
    ]
    assert not found, f"email addresses in responses: {found}"


def test_startup_counts_are_null_unless_the_viewer_is_on_the_team_or_a_founder_on_an_unclaimed_page():
    leaks = []
    for name, _, call in responses():
        body = call["response"]
        if call["request"]["method"] == "GET" and isinstance(body, dict) and "interest_count" in body:
            private = body["view_count"] is not None or body["interest_count"] is not None
            if private and not (body["is_team"] or not body["claimed"]):
                leaks.append(f"{name} {call['request']['path']}")
    assert not leaks, f"startup counts shown to someone who may not see them: {leaks}"


def test_a_startup_page_in_a_non_team_fixture_has_null_counts():
    for name, _, call in responses():
        body = call["response"]
        if name.startswith("startup/") and isinstance(body, dict) and body.get("is_team") is False and body.get("claimed"):
            assert body["view_count"] is None and body["interest_count"] is None, name


def test_join_codes_are_only_sent_to_the_partner_admin():
    for name, doc, call in responses():
        if any(k == "join_code" and v for _, k, v in walk(call["response"])):
            assert doc["persona"] == "meenakshi", f"{name} {call['request']['path']} sends a join code to {doc['persona']}"


def test_under_18_fixtures_carry_no_photos_for_other_people_and_no_unverified_roles():
    for name, _doc, call in responses():
        if not name.endswith("/under_18") or call["status"] >= 400:
            continue
        for p, key, value in walk(call["response"]):
            if key == "photo":
                assert value is None, f"{name} {call['request']['path']}{p}: an under-18 sees a photo"
            if key == "hiring" and value is True:
                continue  # a verified startup: checked against the claimed flag below
        body = call["response"]
        pins = body if isinstance(body, list) else body.get("startups", []) if isinstance(body, dict) else []
        for pin in pins:
            if isinstance(pin, dict) and pin.get("hiring"):
                assert pin["claimed"] is True, f"{name}: an unverified startup shows as hiring to an under-18"


def test_no_under_18_person_appears_in_anyone_elses_fixture():
    minors = {
        "Balaji Fernandes",
        "Dinesh Narayanan",
    }  # seeded under-18 members; the first is the persona of the under_18 fixtures
    for name, _doc, call in responses():
        if name.endswith("/under_18") or call["status"] >= 400:
            continue
        text = json.dumps(call["response"])
        for m in minors:
            assert m not in text, f"{name} {call['request']['path']} shows under-18 member {m}"
