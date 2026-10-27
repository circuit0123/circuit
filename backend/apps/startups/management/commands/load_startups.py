from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.startups import load
from apps.startups.geocode import Nominatim


class Command(BaseCommand):
    geocoder = None  # tests put a fake here; the real run uses Nominatim
    help = "Load startups from a CSV as unclaimed profiles. Safe to run again; never touches claimed startups."

    def add_arguments(self, parser):
        parser.add_argument("csv", type=Path)
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen; write nothing")

    def handle(self, *args, csv, dry_run, **opts):
        if not csv.exists():
            raise CommandError(f"No such file: {csv}")
        try:
            geo = self.geocoder or Nominatim()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        try:
            r = load.load(csv, geo.lookup, dry_run=dry_run)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        w = self.stdout.write
        w("Sector mapping (CSV word -> our sector: rows)")
        for (word, sector), n in sorted(r["sectors"].items()):
            w(f"  {word:<12} -> {sector:<10} {n}")
        for word, sector in r["unknown_sectors"].items():
            w(f"  WARNING: unknown sector '{word}' mapped to closest '{sector}'")
        w(f"{'DRY RUN - nothing written. ' if dry_run else ''}{r['rows']} rows: created {r['created']}, updated {r['updated']}, "
          f"skipped {r['claimed'] + r['other_source'] + r['unchanged']} "
          f"(claimed {r['claimed']}, other source {r['other_source']}, unchanged {r['unchanged']})")  # fmt: skip
        stats = getattr(geo, "stats", {})
        w(f"Geocode: hits {r['pins']}, misses {r['misses']}, no address/area only {r['no_address']}"
          + (f", from cache {stats['cached']}, network errors {stats['errors']}" if stats else ""))  # fmt: skip
