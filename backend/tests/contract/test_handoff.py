"""FRONTEND_HANDOFF.md and the contract tests describe the same API.

Fails when the document names an endpoint that does not exist, when a screen has contract cases but no section (or the other way
round), when a section forgets to name its fixtures, or when a documented hook is not exercised by any case.
"""

import re
from pathlib import Path

from tests.contract import runner, shape
from tests.contract.cases import CASES

DOC = (Path(__file__).resolve().parents[3] / "FRONTEND_HANDOFF.md").read_text()
SCREEN_HEADING = re.compile(r"^### `([a-z_0-9]+)`", re.M)
ENDPOINT = re.compile(r"`(GET|POST|PUT|PATCH|DELETE)((?:\s*\|\s*(?:GET|POST|PUT|PATCH|DELETE))*) (/api/[A-Za-z0-9_/{}.\-]*)")


def sections() -> dict[str, str]:
    marks = list(SCREEN_HEADING.finditer(DOC))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else DOC.index("\n## 2.")
        out[m.group(1)] = DOC[m.start() : end]
    return out


def test_every_screen_with_cases_has_a_section_and_the_other_way_round():
    screens = {c.screen for c in CASES}
    documented = set(sections())
    assert screens - documented == set(), (
        f"screens with contract cases but no section in FRONTEND_HANDOFF.md: {screens - documented}"
    )
    assert documented - screens == set(), f"sections with no contract case: {documented - screens}"


def test_every_endpoint_named_in_the_document_exists():
    known = {(m.upper(), p) for p, item in shape.spec()["paths"].items() for m in item}
    missing = []
    for m in ENDPOINT.finditer(DOC):
        path = re.sub(r"\{[^}]+\}", "{}", m.group(3).rstrip("/.").split("?")[0])
        methods = [m.group(1)] + [x.strip() for x in m.group(2).split("|") if x.strip()]
        for method in methods:
            if (method, path) not in {(a, re.sub(r"\{[^}]+\}", "{}", b)) for a, b in known}:
                missing.append(f"{method} {m.group(3)}")
    assert not missing, f"FRONTEND_HANDOFF.md names endpoints that do not exist: {sorted(set(missing))}"


def test_every_section_names_its_fixture_files():
    problems = []
    for name, text in sections().items():
        scenarios = sorted({c.scenario for c in CASES if c.screen == name})
        for scenario in scenarios:
            if scenario not in text:
                problems.append(f"{name}: scenario '{scenario}' is not mentioned")
        if f"{name}/" not in text:
            problems.append(f"{name}: no 'Fixtures:' line")
    assert not problems, "\n".join(problems)


def test_every_hook_in_a_section_is_exercised_by_a_case():
    hooks_in_cases = {call.hook for c in CASES for call in c.calls}
    problems = []
    for name, text in sections().items():
        line = next((ln for ln in text.splitlines() if ln.startswith("**Hooks:**")), "")
        for hook in re.findall(r"`(use[A-Za-z]+)`", line):
            # a hook followed by "(" has no call of its own, or none a fixture can show; the document says why
            if hook not in hooks_in_cases and not line.split(f"`{hook}`")[1].startswith(" ("):
                problems.append(f"{name}: hook {hook} is documented but no contract case calls it")
    assert not problems, "\n".join(problems)


# Endpoints no screen draws, with the reason. Everything else in openapi.json must appear in a committed fixture.
OUTSIDE_THE_SCREENS = {
    ("GET", "/api/health"): "probe for monitors",
    ("GET", "/api/health/deps"): "probe for monitors",
    ("GET", "/api/demo/personas"): "dev and demo persona switcher only",
    ("POST", "/api/demo/token"): "dev and demo persona switcher only",
    ("GET", "/api/unsubscribe"): "page opened from an email link, outside the app",
    ("POST", "/api/unsubscribe"): "page opened from an email link, outside the app",
    ("GET", "/api/me/export"): "answers differently each day (link expiry); see the settings section",
    ("GET", "/api/me/export/download"): "needs the emailed signed token",
    ("POST", "/api/me/deletion"): "destructive: erases the account",
    ("POST", "/api/me/verify/work-email"): "the code arrives by email",
    ("POST", "/api/me/verify/work-email/confirm"): "the code arrives by email",
    ("POST", "/api/startups/{}/claim/verify"): "the code arrives by email",
    ("POST", "/api/media/uploads/{}/complete"): "needs the uploaded file; the flow is described in the document",
    ("POST", "/api/organisations/join"): "joining by code: covered by the API tests; see the signup section",
    ("POST", "/api/organisations/join-by-email"): "needs a verified college email",
    ("POST", "/api/organisations/leave"): "covered by the API tests",
    ("DELETE", "/api/organisations/mine/members/{}"): "partner admin removes a member: covered by the API tests",
    ("GET", "/api/conversations/{}/messages/{}"): "the fetch after a Realtime nudge: same shape as a message in the list",
}


def _fixture_calls() -> set[tuple[str, str]]:
    import json

    found = set()
    for f in runner.FIXTURES.glob("*/*.json"):
        for call in json.loads(f.read_text())["calls"]:
            req = call["request"]
            path = req["path"].split("?")[0]
            found.add((req["method"], re.sub(r"\{[^}]+\}", "{}", shape.template_for(req["method"], path))))
    return found


def test_every_endpoint_is_drawn_by_a_screen_or_named_as_outside_them():
    ops = {(m.upper(), re.sub(r"\{[^}]+\}", "{}", p)) for p, item in shape.spec()["paths"].items() for m in item}
    uncovered = ops - _fixture_calls() - set(OUTSIDE_THE_SCREENS)
    assert not uncovered, (
        "endpoints no contract case calls (add a call to tests/contract/cases.py, or name it in OUTSIDE_THE_SCREENS with a reason): "
        f"{sorted(uncovered)}"
    )
    stale = set(OUTSIDE_THE_SCREENS) - ops
    assert not stale, f"OUTSIDE_THE_SCREENS lists endpoints that no longer exist: {sorted(stale)}"
