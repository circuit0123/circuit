import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.matching.evaluation import EVAL_DIR, evaluate, load_pairs


class Command(BaseCommand):
    help = "Score the hand-labelled pairs in tests/eval/pairs.json and fail if agreement drops below the recorded baseline."

    def add_arguments(self, parser):
        parser.add_argument("--update-baseline", action="store_true", help="record today's agreement as the new baseline")

    def handle(self, *args, **options):
        agreement, misses = evaluate(load_pairs())
        provider = settings.EMBEDDING_PROVIDER  # similarity scores differ per embedding model, so each has its own baseline
        total = len(load_pairs()["pairs"])
        self.stdout.write(f"agreement {agreement:.3f} ({total - len(misses)}/{total} pairs) with the {provider} embedder")
        for m in misses:
            self.stdout.write(
                f"  MISS {m['member']}: {m['better']} ({m['better_score']}) should beat {m['worse']} ({m['worse_score']}) - {m['why']}"
            )
        path = EVAL_DIR / "baseline.json"
        baseline = json.loads(path.read_text()) if path.exists() else {}
        if options["update_baseline"]:
            path.write_text(json.dumps({**baseline, provider: round(agreement, 4)}, indent=1) + "\n")
            self.stdout.write(f"baseline for {provider} set to {agreement:.4f}")
        elif provider not in baseline:
            self.stdout.write(f"no baseline for {provider} yet: run with --update-baseline once you are happy with the result")
        elif agreement < baseline[provider] - 1e-9:
            raise CommandError(f"agreement fell from {baseline[provider]} to {agreement:.3f}")
        else:
            self.stdout.write(f"OK: not below the baseline of {baseline[provider]}")
