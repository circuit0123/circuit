"""One-off load of researched startups from a CSV as unclaimed, visible profiles (F3). Safe to run again."""

import csv
import difflib
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from django.contrib.gis.geos import Point
from django.db import transaction

from apps.events.services import record
from apps.startups.geocode import MAX_KM_FROM_CITY, km_between
from apps.startups.models import Startup
from core.cities import CITIES
from seed.data import SECTORS

REQUIRED = ("name", "website_domain", "city", "address", "address_note", "description", "sector", "stage", "hiring", "confidence")
DETAIL_COLUMNS = (
    "careers_url",
    "funding_evidence",
    "address_source",
    "address_note",
    "needs_check",
    "scraped_from",
    "scraped_at",
)
CONFIDENCE = {"high": 0.9, "medium": 0.6}
CITY_CENTRES = {name.lower(): (lat, lng) for name, lat, lng in CITIES}

# CSV sector word -> one of our fixed sectors (seed.data.SECTORS)
SECTOR_MAP = {
    **{s: s for s in SECTORS},
    "ai": "deeptech", "spacetech": "deeptech", "climate": "cleantech", "mobility": "logistics",
    "ecommerce": "d2c", "consumer": "d2c", "foodtech": "d2c", "media": "d2c", "gaming": "d2c",
    "proptech": "saas", "hrtech": "saas", "legaltech": "saas", "traveltech": "saas",
}  # fmt: skip

Geocoder = Callable[[str], tuple[float, float] | None]


def map_sector(word: str, unknown: dict[str, str]) -> str:
    word = word.strip().lower()
    if word in SECTOR_MAP:
        return SECTOR_MAP[word]
    close = difflib.get_close_matches(word, list(SECTORS), n=1, cutoff=0.0)
    unknown[word] = close[0]
    return close[0]


def wants_pin(row: dict) -> bool:
    return bool(row["address"].strip()) and "area only" not in row["address_note"].lower()


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(missing)}")
        return [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]


def load(path: Path, geocode: Geocoder, dry_run: bool = False) -> dict:
    rows = read_rows(path)
    out = {
        "created": 0,
        "updated": 0,
        "claimed": 0,
        "other_source": 0,
        "unchanged": 0,
        "pins": 0,
        "no_pin": 0,
        "no_address": 0,
        "misses": 0,
    }
    sectors: Counter[tuple[str, str]] = Counter()
    unknown: dict[str, str] = {}
    with transaction.atomic():
        for row in rows:
            sector = map_sector(row["sector"], unknown)
            sectors[(row["sector"].lower(), sector)] += 1
            _load_row(row, sector, geocode, out)
        if dry_run:
            transaction.set_rollback(True)
    return {**out, "sectors": sectors, "unknown_sectors": unknown, "rows": len(rows)}


def _point(row: dict, geocode: Geocoder, out: dict) -> Point | None:
    """Never invent a pin: no address / area only -> none; a far-away hit -> none."""
    if not wants_pin(row):
        out["no_address"] += 1
        return None
    hit = geocode(row["address"])
    centre = CITY_CENTRES.get(row["city"].lower())
    if hit is None or (centre and km_between(centre, hit) > MAX_KM_FROM_CITY):
        out["misses"] += 1
        return None
    out["pins"] += 1
    return Point(hit[1], hit[0], srid=4326)


def _load_row(row: dict, sector: str, geocode: Geocoder, out: dict) -> None:
    domain = row["website_domain"].lower()
    existing = Startup.objects.filter(website_domain=domain).first()
    if existing and existing.claimed_by_id:
        out["claimed"] += 1
        return
    if existing and existing.source != Startup.Source.CRAWLER:
        out["other_source"] += 1
        return
    wanted = {
        "name": row["name"], "description": row["description"], "sector": sector, "stage": row["stage"],
        "hiring": row["hiring"].lower() == "true", "confidence": CONFIDENCE.get(row["confidence"].lower(), 0.6),
        "details": {c: row[c] for c in DETAIL_COLUMNS if row.get(c)},
    }  # fmt: skip
    if existing is None:
        point = _point(row, geocode, out)
        s = Startup.objects.create(
            website_domain=domain, source=Startup.Source.CRAWLER, address=row["address"], location=point, **wanted
        )
        record(
            "startup.created", target_type="startup", target_id=s.pk, sector=sector, city=row["city"], has_pin=point is not None
        )
        out["created"] += 1
        return
    changed = [f for f, v in wanted.items() if getattr(existing, f) != v]
    for f in changed:
        setattr(existing, f, wanted[f])
    if not existing.location and existing.address in ("", row["address"]):  # a pin or address set by a person is never replaced
        point = _point(row, geocode, out)
        if point:
            existing.location, existing.address = point, row["address"]
            changed += ["location", "address"]
    if changed:
        existing.save(update_fields=changed)
        out["updated"] += 1
    else:
        out["unchanged"] += 1
