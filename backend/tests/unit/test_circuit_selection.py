"""Choosing circuits on hand-built graphs: no database."""

from ortools.sat.python import cp_model

from apps.circuits import services


def test_nothing_to_choose():
    assert services.select_cycles([]) == []


def test_disjoint_loops_are_all_chosen():
    assert services.select_cycles([((1, 2, 3), 0.5), ((4, 5, 6), 0.4)]) == [0, 1]


def test_overlapping_loops_pick_the_best_total():
    cycles = [((1, 2, 3), 0.9), ((3, 4, 5), 0.5), ((4, 5, 6), 0.6)]
    assert services.select_cycles(cycles) == [0, 2]  # 1.5 beats 0.9 + nothing and beats 0.5 + 0.9 (they share member 3)


def test_the_solver_beats_greedy_when_the_best_single_loop_blocks_two_good_ones():
    cycles = [((1, 2, 3), 0.6), ((1, 4, 5), 0.5), ((2, 6, 7), 0.5)]
    assert services.greedy_cycles(cycles) == [0]  # takes the 0.6 loop and blocks both others
    assert services.select_cycles(cycles) == [1, 2]  # 1.0 in total


def test_same_input_same_answer():
    cycles = [((i, i + 1, i + 2), 0.5) for i in range(1, 12)]  # a chain of overlapping loops, all equally good
    first = services.select_cycles(cycles)
    assert all(services.select_cycles(cycles) == first for _ in range(3))
    used = [m for i in first for m in cycles[i][0]]
    assert len(used) == len(set(used))  # nobody twice


def test_greedy_fallback_when_the_solver_gives_up(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda self, model: cp_model.UNKNOWN)
    assert services.select_cycles([((1, 2, 3), 0.6), ((1, 4, 5), 0.5), ((2, 6, 7), 0.5)]) == [0]


def test_a_loop_is_as_good_as_its_weakest_handover():
    scores = {(1, 2): 0.9, (2, 3): 0.4, (3, 1): 0.7}
    assert services.weakest_link(scores, (1, 2, 3)) == 0.4


def test_iso_week_label():
    from datetime import datetime

    assert services.iso_week(datetime(2026, 10, 23)) == "2026-W43"
    assert services.iso_week(datetime(2026, 1, 1)) == "2026-W01"
