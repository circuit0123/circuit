"""The Ranker interface: given the features for a member's candidates, return one number per candidate (higher = better)."""

from typing import Protocol


class Ranker(Protocol):
    name: str  # "rule" or "model"
    version: str  # "" for the rule, the ModelVersion.version for a model

    def score(self, rows: list[dict]) -> list[float]:
        """`rows` are feature dicts (each also carries `rule_score` under the key "rule_score"); returns scores in the same order."""
        ...
