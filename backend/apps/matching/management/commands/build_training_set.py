import csv

from django.core.management.base import BaseCommand

from apps.matching.ranker import features as feat
from apps.matching.ranker import training


class Command(BaseCommand):
    help = "Build the training set from feature snapshots and intro outcomes, and print what is in it. --out writes ids and features to a CSV."

    def add_arguments(self, parser):
        parser.add_argument("--out", help="write snapshot id, label and features to this CSV file")

    def handle(self, *args, **opts):
        ds = training.build_training_set()
        self.stdout.write(
            f"{len(ds.labels)} rows in {ds.groups} lists ({ds.real_rows} real, {ds.simulated_rows} simulated); labels {ds.histogram()}"
        )
        if opts["out"]:
            with open(opts["out"], "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["snapshot_id", "label", *feat.FEATURE_NAMES])
                for sid, label, f in zip(ds.snapshot_ids, ds.labels, ds.features):
                    w.writerow([sid, label, *[f.get(k) for k in feat.FEATURE_NAMES]])
            self.stdout.write(f"wrote {opts['out']}")
