"""Synthetic network for testing the ML pipeline end to end (`manage.py simulate_network`).

Synthetic members have hidden tastes (how much they care about fit, distance, verification), see lists the rule ranker
made, and answer intros by those tastes. That gives labelled data before any real member exists. A model trained on it
shows the pipeline works; it says nothing about real people, so it is NEVER served to real members (ranker/guard.py).

Simulated members live in their own world (`Member.is_simulated`): matching, circuits and feeds never mix them with real
members. Only IntroRequest rows and snapshots are written, no events and no notifications, so product analytics stay clean.
"""

import json
import math
import random
import uuid
from datetime import datetime, time, timedelta

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Connection, Member
from apps.intros.models import IntroRequest
from apps.matching import services
from apps.matching.models import Capability, FeatureSnapshot, MemberTrait, Need, Offer, Trait
from apps.matching.ranker import training
from apps.matching.ranker.serving import Serving
from core import ist

CITY = "Simulation"
CENTRE = (12.0, 80.0)  # far from the seeded pilot city
ROLES = ["student"] * 6 + ["founder"] * 2 + ["mentor", "investor"]
SHOWN_PER_ROUND = 8


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def exists() -> bool:
    return Member.objects.filter(is_simulated=True).exists()


def remove() -> int:
    """Delete every simulated member; their needs, offers, intros, matches and snapshots go with them (cascade)."""
    deleted, _ = Member.objects.filter(is_simulated=True).delete()
    return deleted


def create_members(count: int, rng: random.Random) -> dict[int, dict]:
    """Members, needs, offers, traits and connections. Returns each member's hidden tastes."""
    caps = list(Capability.objects.values_list("pk", "name"))
    traits = list(Trait.objects.values_list("pk", flat=True))
    colleges = list(json.loads(training.TIERS_FILE.read_text())["tiers"])
    members = []
    for i in range(count):
        role = rng.choice(ROLES)
        spread = 0.1 if rng.random() < 0.7 else 0.35  # most live close together, some far away (about 40 km)
        members.append(
            Member(
                auth_user_id=uuid.UUID(int=rng.getrandbits(128), version=4), role=role, display_name=f"Simulated {i}",
                city=CITY, college=rng.choice(colleges) if role == "student" else "", is_simulated=True,
                location=Point(CENTRE[1] + rng.uniform(-spread, spread), CENTRE[0] + rng.uniform(-spread, spread), srid=4326),
                verification_level=rng.choice([1, 1, 2, 3]), open_intro_slots=rng.choice([1, 2, 3, 3]),
            )
        )  # fmt: skip
    Member.objects.bulk_create(members)
    members = list(Member.objects.filter(is_simulated=True).order_by("pk"))
    needs, offers, mtraits = [], [], []
    for m in members:
        for pk, name in rng.sample(caps, rng.randint(1, 3)):
            needs.append(Need(member=m, capability_id=pk, description=f"Looking for help with {name.lower()}"))
        for pk, name in rng.sample(caps, rng.randint(1, 3)):
            offers.append(Offer(member=m, capability_id=pk, description=f"Can help with {name.lower()}"))
        mtraits += [MemberTrait(member=m, trait_id=t) for t in rng.sample(traits, rng.randint(0, min(4, len(traits))))]
    Need.objects.bulk_create(needs)
    Offer.objects.bulk_create(offers)
    MemberTrait.objects.bulk_create(mtraits)
    pairs: set[tuple[int, int]] = set()
    ids = [m.pk for m in members]
    for a in ids:
        for b in rng.sample(ids, min(4, len(ids))):
            if a != b:
                pairs.add((min(a, b), max(a, b)))
    Connection.objects.bulk_create(
        [Connection(member_a_id=a, member_b_id=b, strength=round(rng.uniform(0.2, 1.0), 2), source="simulation") for a, b in sorted(pairs)]
    )  # fmt: skip
    return {
        m.pk: {
            "fit": rng.uniform(0.5, 1.5),
            "near": rng.uniform(0.0, 1.0),
            "trust": rng.uniform(0.0, 1.0),
            "level": rng.uniform(0.0, 0.6),
        }
        for m in members
    }  # hidden tastes


def _wants(f: dict, taste: dict) -> float:
    """How much the viewer wants this candidate, by their own tastes. Deliberately not the rule's formula."""
    dist = f["distance_km"] if f["distance_km"] is not None else 25.0
    return (
        taste["fit"] * 3.0 * f["comp_they_give"]
        - taste["near"] * dist / 15.0
        + taste["trust"] * 1.5 * f["trust_path"]
        + taste["level"] * (f["candidate_level"] - 1)
        + 0.5 * f["embedding_similarity"]
    )


def _says_yes(f: dict, taste: dict) -> float:
    """The candidate's side: do they want to help this viewer? Looks at what the viewer can give back, and verification."""
    return _sigmoid(taste["fit"] * 2.0 * f["comp_i_give"] + taste["level"] * (f["viewer_level"] - 1) - 0.8)


def simulate(members: int = 400, rounds: int = 14, seed: int = 7) -> dict:
    rng = random.Random(seed)
    with transaction.atomic():
        tastes = create_members(members, rng)
        services.backfill_embeddings()
    now = timezone.now()
    ctx = services.make_context(
        now, simulated=True, serving=Serving()
    )  # the rule ranks: unbiased data for the model to learn from
    lists = {mid: services.rank_member(ctx, mid) for mid in sorted(ctx.world.members)}
    tz = ist.tz()
    snaps: list[FeatureSnapshot] = []
    intros: list[IntroRequest] = []
    whens: list[datetime] = []
    asked: set[tuple[int, int]] = set()
    for r in range(rounds):
        day = (now - timedelta(days=rounds - r)).astimezone(tz).date()
        shown_at = datetime.combine(day, time(8), tzinfo=tz)
        for viewer, ranked in lists.items():
            if not ranked:
                continue
            picked = sorted(rng.sample(range(len(ranked)), min(SHOWN_PER_ROUND, len(ranked))))
            for pos, idx in enumerate(picked):
                row = ranked[idx]
                snaps.append(
                    FeatureSnapshot(
                        viewer_id=viewer, candidate_id=row.candidate_id, surface="simulation", arm="rule", features=row.features,
                        position=pos, rule_score=row.ps.score, shown_at=shown_at, shown_on=day,
                    )
                )  # fmt: skip
                f = row.features
                if (viewer, row.candidate_id) in asked or rng.random() >= _sigmoid(_wants(f, tastes[viewer]) - 2.2):
                    continue
                asked.add((viewer, row.candidate_id))
                when = shown_at + timedelta(minutes=rng.randint(5, 600))
                accepted = rng.random() < _says_yes(f, tastes[row.candidate_id])
                rating = None
                if accepted and rng.random() < 0.7:
                    rating = max(1, min(5, round(1.5 + 3.5 * f["complementarity"] + rng.gauss(0, 0.8))))
                intros.append(
                    IntroRequest(
                        requester_id=viewer, target_id=row.candidate_id, status="completed" if rating else "accepted" if accepted else "declined",
                        stage="done", expires_at=when + timedelta(days=7), outcome_rating=rating, responded_at=when + timedelta(hours=3),
                    )
                )  # fmt: skip
                whens.append(when)
    with transaction.atomic():
        FeatureSnapshot.objects.bulk_create(snaps, batch_size=2000)
        IntroRequest.objects.bulk_create(intros, batch_size=2000)
        for i, when in zip(intros, whens):  # auto_now_add ignores a value given at create; set the real time afterwards
            i.created_at = when
        IntroRequest.objects.bulk_update(intros, ["created_at"], batch_size=2000)
    return {"members": len(tastes), "snapshots": len(snaps), "intros": len(intros), "rounds": rounds}
