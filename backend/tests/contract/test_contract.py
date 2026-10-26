"""Contract tests: every screen's calls, against the real API, as FRONTEND_HANDOFF.md describes them.

One test makes the demo world once (about 10 seconds) and runs every case in order, because the cases build on each other (Asha
accepts a circuit, then Priya, then it is active). Each response is checked against the OpenAPI description and compared with its
committed fixture; the frontend's mock mode serves the same fixtures. After a deliberate API change run `make contract-fixtures`.
"""

import json

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.matching import services as matching
from apps.social.drop import build_all
from seed.build import run
from tests.contract import runner
from tests.contract.cases import CASES

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch):
    """The demo seed at a frozen clock, with matches, this week's circuit round and today's drops built, like the demo environment."""
    monkeypatch.setattr(timezone, "now", lambda: runner.FROZEN)
    run(settings.SEED_CITY)
    matching.compute_all()
    call_command("run_circuit_round")
    build_all(runner.FROZEN)
    from core.llm import FakeLLM, set_llm

    set_llm(
        FakeLLM(
            json.dumps(
                {
                    "needs": ["performance-marketing"],
                    "offers": ["frontend-dev"],
                    "skills": ["frontend-dev"],
                    "traits": [],
                }
            )
        )
    )
    return runner.World()


def test_every_screen_matches_the_api_and_its_fixture(world, client_for, settings):
    problems: list[str] = []
    docs = {}
    for case in CASES:
        doc, found = runner.run_case(case, world, client_for, settings)
        problems += found
        docs[(case.screen, case.scenario)] = doc
        if not found:
            note = runner.compare_or_write(case, doc)
            if note:
                problems.append(note)
    if runner.UPDATE:
        (runner.FIXTURES / "index.json").write_text(runner.build_index(CASES))
        for stale in runner.stale_files(CASES):
            (runner.FIXTURES / stale).unlink()
    elif (runner.FIXTURES / "index.json").read_text() != runner.build_index(CASES):
        problems.append("fixtures/index.json is out of date: run `make contract-fixtures`")
    else:
        problems += [f"fixtures/{f} belongs to no case any more: run `make contract-fixtures`" for f in runner.stale_files(CASES)]
    assert not problems, "\n" + "\n".join(problems)
