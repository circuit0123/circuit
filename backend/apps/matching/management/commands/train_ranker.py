import hashlib
import json

import structlog
from django.conf import settings
from django.utils import timezone

from apps.events.services import record
from apps.matching.models import ModelVersion
from apps.matching.ranker import training
from core.jobs import JobCommand
from core.storage import get_storage

log = structlog.get_logger("jobs")


class Command(JobCommand):
    help = (
        "Train a candidate ranker from the feature snapshots, evaluate it against the rule ranker, and save it (private bucket + "
        "model_versions). It never changes what members see: a super admin promotes it in Django admin. Safe to run again."
    )

    lock_minutes = 70  # the job's timeout is an hour

    def summary(self, result: dict) -> str:
        return result["message"]

    def run(self) -> dict:
        ds = training.build_training_set()
        if ds.groups < settings.RANKER_MIN_GROUPS:
            return {
                "skip_reason": "not enough data",
                "groups": ds.groups,
                "message": f"skipped: not enough data ({ds.groups} lists, need {settings.RANKER_MIN_GROUPS})",
            }
        if not any(ds.labels):
            return {
                "skip_reason": "no positive labels",
                "message": "skipped: nobody has asked for an intro yet, so there is nothing to learn from",
            }
        data_hash = ds.data_hash()
        if ModelVersion.objects.filter(data_hash=data_hash).exists():
            return {"skip_reason": "same data", "message": "skipped: a model was already trained on exactly this data"}
        trained = training.train(ds)
        now = timezone.now()
        version = f"v{now:%Y%m%d%H%M%S}-{data_hash[:6]}"
        data = trained.model_text.encode()
        path = f"ml/models/{version}/model.txt"
        storage, bucket = get_storage(), settings.STORAGE_BUCKETS["ml"]
        storage.put(bucket, path, data, "text/plain")

        storage.put(
            bucket, f"ml/models/{version}/metrics.json", json.dumps(trained.metrics, indent=1).encode(), "application/json"
        )
        source = "real" if not ds.simulated_rows else "simulated" if not ds.real_rows else "mixed"
        mv = ModelVersion.objects.create(
            version=version, trained_at=now, metrics=trained.metrics, file_path=path, sha256=hashlib.sha256(data).hexdigest(),
            data_source=source, real_rows=ds.real_rows, simulated_rows=ds.simulated_rows, trained_env=settings.ENV,
            data_hash=data_hash, beats_rule=trained.beats_rule, fairness_passed=trained.fairness_passed,
        )  # fmt: skip
        record(
            "ranker.trained",
            target_type="model_version",
            target_id=mv.pk,
            version=version,
            data_source=source,
            beats_rule=mv.beats_rule,
        )
        log.info("train_ranker", version=version, data_source=source, beats_rule=mv.beats_rule, fairness=mv.fairness_passed)
        m, r = trained.metrics["model"], trained.metrics["rule"]
        message = (
            f"trained {version} on {source} data ({ds.groups} lists): ndcg@10 {m['ndcg@10']} vs rule {r['ndcg@10']}, "
            f"acceptance@3 {m['acceptance@3']} vs {r['acceptance@3']}, eval agreement {m['eval_agreement']} vs {r['eval_agreement']}; "
            f"beats rule: {mv.beats_rule}, fairness: {mv.fairness_passed}. Saved as a candidate."
        )
        return {"groups": ds.groups, "beats_rule": mv.beats_rule, "fairness_passed": mv.fairness_passed, "message": message}
