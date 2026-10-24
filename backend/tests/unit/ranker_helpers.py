"""Shared helpers for the ranker tests: model rows, and a tiny real LightGBM model stored the way train_ranker stores one."""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.matching.models import ModelVersion
from apps.matching.ranker import features as feat
from core.storage import get_storage

_n = 0


def make_model(**over) -> ModelVersion:
    """A model row. Defaults: a candidate that beats the rule and passes fairness, trained on real data in production."""
    global _n
    _n += 1
    fields = dict(
        version=f"v-test-{_n}", trained_at=timezone.now() - timedelta(minutes=_n), status="candidate", metrics={},
        file_path=f"ml/models/v-test-{_n}/model.txt", sha256="0" * 64, data_source="real", real_rows=500, simulated_rows=0,
        trained_env="production", data_hash=f"hash-{_n}", beats_rule=True, fairness_passed=True,
    )  # fmt: skip
    fields.update(over)
    return ModelVersion.objects.create(**fields)


def store_booster(mv: ModelVersion, seed: int = 1, rows: int = 400, names: list[str] | None = None) -> ModelVersion:
    """Train a tiny LambdaRank model on random numbers, save it in (memory) storage and point `mv` at it."""
    import lightgbm as lgb
    import numpy as np

    rng = np.random.default_rng(seed)
    X = rng.random((rows, len(feat.FEATURE_NAMES)))
    y = (X[:, 0] * 3).astype(int)
    params = {"objective": "lambdarank", "verbose": -1, "num_threads": 1, "min_data_in_leaf": 5, "seed": seed}
    booster = lgb.train(
        params, lgb.Dataset(X, y, group=[10] * (rows // 10), feature_name=names or list(feat.FEATURE_NAMES)), num_boost_round=5
    )
    data = booster.model_to_string().encode()
    get_storage().put(settings.STORAGE_BUCKETS["ml"], mv.file_path, data, "text/plain")
    ModelVersion.objects.filter(pk=mv.pk).update(sha256=hashlib.sha256(data).hexdigest())
    mv.refresh_from_db()
    return mv
