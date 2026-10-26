"""Run contract cases against the seeded demo world and compare each with its committed fixture.

A case is one screen in one scenario: a persona and the calls the screen's hooks make, in order. Every response is checked
against the OpenAPI description, then written to (or compared with) packages/api-client/fixtures/<screen>/<scenario>.json.
The frontend's mock mode serves those same files, so the mocks cannot drift from the real API.

    make contract-fixtures      rewrite the fixture files after a deliberate API change (commit the diff)
    make check                  fails when the API and the committed fixtures disagree
"""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from apps.accounts.models import Member
from tests.contract import shape

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "api-client" / "fixtures"
FROZEN = datetime(2026, 3, 2, 4, 0, tzinfo=UTC)  # Monday 09:30 IST: the clock every fixture is made at
UPDATE = os.environ.get("UPDATE_FIXTURES") == "1"


@dataclass
class Call:
    hook: str  # the data hook in apps/app/src/data that makes this call
    method: str
    path: str | Callable  # a string, or a function of the World for ids that only exist after seeding
    body: object = None
    status: int = 200
    ignore: tuple[str, ...] = ()  # keys whose values are random per run (codes, tokens): replaced by "<random>"


@dataclass
class Case:
    screen: str
    scenario: str
    persona: str | Callable | None  # a persona key ("ravi"), a function of the World returning a Member, or None = signed out
    calls: list[Call] = field(default_factory=list)
    features: str | None = None  # FEATURES setting for this case (None = everything on, like the dev environment)
    overrides: dict = field(default_factory=dict)  # other Django settings for this case (BETA_MODE, RATE_LIMITS...)
    note: str = ""


def scrub(value, ignore: tuple[str, ...]):
    """Replace values that change every run. Everything else must be identical or the fixture test fails."""
    if isinstance(value, dict):
        return {k: ("<random>" if k in ignore else scrub(v, ignore)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, ignore) for v in value]
    if isinstance(value, str):
        return re.sub(r"[0-9a-f]{32}", "<hex>", value)  # upload folders contain a uuid
    return value


def fixture_path(case: Case) -> Path:
    return FIXTURES / case.screen / f"{case.scenario}.json"


def run_case(case: Case, world, client_for, settings) -> tuple[dict, list[str]]:
    """Make the case's calls; return (the fixture document, problems found)."""
    from core import flags

    settings.FEATURES = case.features or ",".join(f"{n}:everyone" for n in flags.FLAGS)
    saved = {k: getattr(settings, k) for k in case.overrides}
    for key, value in case.overrides.items():
        setattr(settings, key, {**saved[key], **value} if isinstance(value, dict) else value)
    member = None
    if case.persona is not None:
        member = world.member(case.persona) if isinstance(case.persona, str) else case.persona(world)
    client = client_for(member) if member else client_for()
    world.current = member  # body functions that need the caller (an upload owned by them) read this
    problems: list[str] = []
    calls = []
    for call in case.calls:
        path = call.path(world) if callable(call.path) else call.path
        body = call.body(world) if callable(call.body) else call.body
        label = f"{case.screen}/{case.scenario}: {call.method} {path}"
        if body is None:
            response = client.generic(call.method, path)
        else:
            response = client.generic(call.method, path, json.dumps(body), content_type="application/json")
        data = json.loads(response.content) if response.content else None
        if response.status_code != call.status:
            problems.append(f"{label}: expected {call.status}, got {response.status_code} {str(data)[:200]}")
            continue
        problems += [f"{label}: {p}" for p in shape.check_response(call.method, path.split("?")[0], response.status_code, data)]
        calls.append(
            {
                "hook": call.hook,
                "request": {"method": call.method, "path": path, **({"body": body} if body is not None else {})},
                "status": response.status_code,
                "response": scrub(data, call.ignore),
            }
        )
    for key, value in saved.items():
        setattr(settings, key, value)
    persona = case.persona if isinstance(case.persona, str) else ("custom" if case.persona else None)
    doc = {"screen": case.screen, "scenario": case.scenario, "persona": persona, "calls": calls}
    return doc, problems


def compare_or_write(case: Case, doc: dict) -> str | None:
    """None when the committed fixture matches (or was just rewritten); else a message."""
    path = fixture_path(case)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return None
    if not path.exists():
        return f"{path.relative_to(FIXTURES.parent.parent.parent)} does not exist: run `make contract-fixtures`"
    if path.read_text() != text:
        return (
            f"{path.relative_to(FIXTURES.parent.parent.parent)} is out of date: run `make contract-fixtures` and commit the diff"
        )
    return None


def stale_files(cases: list[Case]) -> list[str]:
    """Fixture files that no case produces any more."""
    wanted = {fixture_path(c) for c in cases} | {FIXTURES / "index.json"}
    return sorted(str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob("*.json") if p not in wanted) if FIXTURES.exists() else []


def build_index(cases: list[Case]) -> str:
    """screens -> scenarios -> the hooks each calls: what the mock layer reads first."""
    index: dict = {}
    for c in cases:
        index.setdefault(c.screen, {})[c.scenario] = sorted({call.hook for call in c.calls})
    return json.dumps(index, indent=2, sort_keys=True) + "\n"


class World:
    """The seeded demo world plus helpers to find things in it."""

    current: Member | None = None

    def __init__(self) -> None:
        from seed.personas import auth_uuid

        self._auth_uuid = auth_uuid

    def member(self, key: str) -> Member:
        return Member.objects.get(auth_user_id=self._auth_uuid(key))

    def newbie(self, named: bool = False) -> Member:
        """A brand-new student with nothing yet. `named` = a finished profile with a name and city but no needs, offers or matches."""
        import uuid

        self._newbies = getattr(self, "_newbies", 0) + 1
        return Member.objects.create(
            auth_user_id=uuid.uuid5(uuid.NAMESPACE_URL, f"circuit-contract:newbie:{self._newbies}"),
            role="student",
            display_name="Meera Rao" if named else "",
            city="Chennai" if named else "",
        )
