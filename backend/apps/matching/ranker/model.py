"""ModelRanker: a LightGBM LambdaRank model loaded from private storage. Any failure raises; the caller falls back to the rule.

lightgbm and numpy are imported here, inside functions, so the API process (which never ranks) does not load them.
"""

import hashlib

from django.conf import settings

from apps.matching.ranker.features import FEATURE_NAMES, to_row
from core.storage import get_storage


class ModelRanker:
    name = "model"

    def __init__(self, version: str, booster) -> None:
        self.version = version
        self._booster = booster

    @classmethod
    def load(cls, mv) -> "ModelRanker":
        import lightgbm as lgb

        data = get_storage().get(settings.STORAGE_BUCKETS["ml"], mv.file_path)
        if hashlib.sha256(data).hexdigest() != mv.sha256:
            raise ValueError(f"{mv.version}: model file does not match its recorded hash")
        booster = lgb.Booster(model_str=data.decode())
        if list(booster.feature_name()) != list(FEATURE_NAMES):
            raise ValueError(f"{mv.version}: model was trained on different features")
        return cls(mv.version, booster)

    def score(self, rows: list[dict]) -> list[float]:
        import numpy as np

        if not rows:
            return []
        out = self._booster.predict(np.array([to_row(r) for r in rows], dtype=float))
        return [float(x) for x in out]
