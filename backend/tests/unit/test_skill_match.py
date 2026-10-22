from apps.matching.scoring import skill_match


def test_full_marks_for_top_level_on_everything_required():
    assert skill_match({1: 3, 2: 3}, {1, 2}) == 1.0


def test_no_overlap_is_zero():
    assert skill_match({9: 3}, {1, 2}, {3}) == 0.0


def test_level_one_counts_less_than_level_three():
    assert skill_match({1: 1}, {1}) == 0.6
    assert skill_match({1: 2}, {1}) == 0.8
    assert skill_match({1: 3}, {1}) == 1.0


def test_half_of_required_covered():
    assert skill_match({1: 3}, {1, 2}) == 0.5


def test_optional_carries_a_fifth():
    # required fully met (1.0 * 0.8) + optional untouched
    assert skill_match({1: 3}, {1}, {2}) == 0.8
    assert skill_match({1: 3, 2: 3}, {1}, {2}) == 1.0


def test_only_optional_uses_all_of_the_score():
    assert skill_match({2: 3}, set(), {2}) == 1.0


def test_nothing_wanted_is_zero():
    assert skill_match({1: 3}, set(), set()) == 0.0


def test_levels_above_three_are_capped():
    assert skill_match({1: 9}, {1}) == 1.0
