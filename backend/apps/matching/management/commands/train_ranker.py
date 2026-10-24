import hashlib
import json

import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.events.services import record
from apps.matching.models import ModelVersion
from apps.matching.ranker import training
from core.storage import get_storage

log = structlog.get_logger("jobs")


class Command(BaseCommand):
    help = (
        "Train a candidate ranker from the feature snapshots, evaluate it against the rule ranker, and save it (private bucket + "
        "model_versions). It never changes what members see: a super admin promotes it in Django admin. Safe to run again."
    )

    def handle(self, *args, **options):
        ds = training.build_training_set()
        if ds.groups < settings.RANKER_MIN_GROUPS:
            log.info("train_ranker", skipped="not enough data", groups=ds.groups)
            self.stdout.write(f"skipped: not enough data ({ds.groups} lists, need {settings.RANKER_MIN_GROUPS})")
            return
        if not any(ds.labels):
            log.info("train_ranker", skipped="no positive labels")
            self.stdout.write("skipped: nobody has asked for an intro yet, so there is nothing to learn from")
            return
        data_hash = ds.data_hash()
        if ModelVersion.objects.filter(data_hash=data_hash).exists():
            log.info("train_ranker", skipped="same data")
            self.stdout.write("skipped: a model was already trained on exactly this data")
            return
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
        self.stdout.write(
            f"trained {version} on {source} data ({ds.groups} lists): ndcg@10 {m['ndcg@10']} vs rule {r['ndcg@10']}, "
            f"acceptance@3 {m['acceptance@3']} vs {r['acceptance@3']}, eval agreement {m['eval_agreement']} vs {r['eval_agreement']}; "
            f"beats rule: {mv.beats_rule}, fairness: {mv.fairness_passed}. Saved as a candidate."
        )
