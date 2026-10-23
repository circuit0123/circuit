"""The matching eval set: scoring changes must not lower agreement with the hand-labelled pairs."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.matching.evaluation import EVAL_DIR, evaluate, load_pairs


def test_pairs_file_is_well_formed():
    data = load_pairs()
    assert len(data["pairs"]) >= 12
    for pair in data["pairs"]:
        assert {pair["member"], pair["better"], pair["worse"]} <= set(data["profiles"]) and pair["why"]
    for key in data["links"]:
        assert set(key.split("|")) <= set(data["profiles"])


def test_agreement_is_not_below_the_recorded_baseline(settings):
    baseline = json.loads((EVAL_DIR / "baseline.json").read_text())
    agreement, misses = evaluate(load_pairs())
    assert agreement >= baseline[settings.EMBEDDING_PROVIDER], misses


def test_the_eval_can_fail(settings):
    """A broken scorer must show up: with trust and traits ignored, the pairs that rest on them are missed."""
    settings.MATCH_WEIGHTS = {**settings.MATCH_WEIGHTS, "trust_path": 0, "affinity": 0}
    agreement, misses = evaluate(load_pairs())
    assert agreement < 1 and {m["why"] for m in misses} >= {"a direct connection beats a stranger"}


def test_command_passes_and_fails_against_the_baseline(settings, capsys):
    call_command("eval_matching")
    assert "OK" in capsys.readouterr().out
    settings.MATCH_WEIGHTS = {**settings.MATCH_WEIGHTS, "trust_path": 0}
    with pytest.raises(CommandError, match="fell"):
        call_command("eval_matching")
