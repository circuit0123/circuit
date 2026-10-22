"""Pure scoring functions: no database, no network, so they are easy to test on hand-built examples."""


def skill_match(skills: dict[int, int], required: set[int], optional: set[int] | None = None) -> float:
    """How well a student's skills cover a job or startup, 0..1.

    `skills` maps capability id -> level (1-3). Required capabilities carry 80% of the score and optional ones 20%;
    a level-1 skill counts 0.6, level 2 counts 0.8, level 3 counts 1.0. With nothing required, only optional counts.
    The college is never an input: matching is on skills and proof of work.
    """
    optional = optional or set()

    def coverage(wanted: set[int]) -> float:
        if not wanted:
            return 0.0
        return sum(0.4 + 0.2 * min(skills[c], 3) for c in wanted if c in skills) / len(wanted)

    if required and optional:
        return round(0.8 * coverage(required) + 0.2 * coverage(optional), 4)
    if required:
        return round(coverage(required), 4)
    return round(coverage(optional), 4)
