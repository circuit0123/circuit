"""RuleRanker: the v1 formula. It is the fallback for every error and the baseline every model must beat."""


class RuleRanker:
    name = "rule"
    version = ""

    def score(self, rows: list[dict]) -> list[float]:
        return [r["rule_score"] for r in rows]
