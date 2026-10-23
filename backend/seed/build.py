"""Deterministic seed builder. Same input -> same rows, so reset_demo is idempotent."""

import random
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest, Consent, Member
from apps.jobs.models import Application, Job, JobCapability
from apps.matching.lists import sync_lists
from apps.matching.models import Capability, MemberSkill, MemberTrait, Need, Offer, Trait
from apps.messaging.models import Conversation, Message
from apps.organisations.models import Organisation
from apps.social.models import Follow, MediaUpload, Post, PostMedia, Reaction, Reply
from apps.startups.models import Startup, StartupMember, StartupTrait
from core.embeddings import get_embedder
from core.storage import get_storage
from seed import data, mockups
from seed.personas import PERSONAS, auth_uuid

SEED = 42
N_STUDENTS, N_FOUNDERS, N_MENTORS, N_INVESTORS, N_STARTUPS = 250, 30, 10, 8, 150
APP_LABELS = [
    "circuits",
    "intros",
    "jobs",
    "matching",
    "moderation",
    "notifications",
    "startups",
    "accounts",
    "organisations",
    "events",
    "social",
    "messaging",
]
KEEP_TABLES = {"matching_capability", "matching_trait"}  # fixed lists survive a reset


def reset_tables() -> None:
    """TRUNCATE all domain tables (fast, and allowed on the append-only events table)."""
    from django.apps import apps

    tables = [
        m._meta.db_table
        for label in APP_LABELS
        for m in apps.get_app_config(label).get_models()
        if m._meta.db_table not in KEEP_TABLES
    ]
    with connection.cursor() as cur:
        cur.execute("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE")


class Seeder:
    def __init__(self, city: dict):
        self.rnd = random.Random(SEED)
        self.city = city
        self.cap: dict[str, Capability] = {}
        self.trait: dict[str, Trait] = {}
        self.members: dict[str, Member] = {}  # persona key -> Member
        self.startups: dict[str, Startup] = {}
        self.needs: list[tuple[Member, str, str]] = []
        self.offers: list[tuple[Member, str, str]] = []
        self.org: Organisation
        self.used_domains: set[str] = set()
        self.member_traits_extra: dict[str, list[str]] = {}
        self.skill_overrides: dict = {}
        self.fixed_connections: list[tuple[str, str, float]] = []

    # -- helpers ---------------------------------------------------------
    def point(self, area_idx: int | None = None) -> Point:
        name, dlat, dlng = data.AREAS[area_idx if area_idx is not None else self.rnd.randrange(len(data.AREAS))]
        return Point(
            self.city["lng"] + dlng + self.rnd.uniform(-0.01, 0.01),
            self.city["lat"] + dlat + self.rnd.uniform(-0.01, 0.01),
            srid=4326,
        )

    def person_name(self) -> str:
        return f"{self.rnd.choice(data.FIRST_NAMES)} {self.rnd.choice(data.LAST_NAMES)}"

    def new_member(self, key: str | None, role: str, name: str, i: int, **kw) -> Member:
        return Member(
            auth_user_id=auth_uuid(key or f"{role}-{i}"),
            role=role,
            display_name=name,
            city=self.city["name"],
            location=self.point(),
            **kw,
        )

    def add_needs_offers(self, member: Member, needs: list[str], offers: list[str]) -> None:
        for slug in needs:
            self.needs.append((member, slug, f"Looking for help with {self.cap[slug].name.lower()}"))
        for slug in offers:
            self.offers.append((member, slug, f"Can help with {self.cap[slug].name.lower()}"))

    def make_startup(self, name: str, sector: str, hiring: bool, domain: str | None = None) -> Startup:
        domain = domain or f"{name.lower().replace(' ', '')}.in"
        while domain in self.used_domains:
            domain = domain.replace(".in", "x.in")
        self.used_domains.add(domain)
        area = self.rnd.randrange(len(data.AREAS))
        s = Startup(
            name=name,
            website_domain=domain,
            sector=sector,
            hiring=hiring,
            stage=self.rnd.choice(["idea", "prototype", "seed", "seed", "series-a"]),
            description=f"{name} builds {sector} products for Indian customers.",
            address=f"{data.AREAS[area][0]}, {self.city['name']}",
            location=self.point(area),
            tech_stack=self.rnd.sample(["python", "react", "postgres", "flutter", "aws", "tensorflow", "arduino"], 3),
            source="seed",
            confidence=round(self.rnd.uniform(0.7, 1.0), 2),
            view_count=self.rnd.randrange(0, 60),
        )
        return s

    # -- build ----------------------------------------------------------
    @transaction.atomic
    def run(self) -> dict:
        reset_tables()
        sync_lists(Capability, Trait)
        self.cap = {c.slug: c for c in Capability.objects.all()}
        self.trait = {t.slug: t for t in Trait.objects.all()}
        self.build_org()
        self.build_story_cast()
        self.build_bulk_members()
        self.build_startups_and_jobs()
        self.build_stories()
        self.save_skills_traits()
        self.save_needs_offers()
        self.build_connections()
        self.build_consents()
        self.build_social()
        return {"members": Member.objects.count(), "startups": Startup.objects.count(), "jobs": Job.objects.count()}

    def build_org(self) -> None:
        self.org = Organisation.objects.create(
            name=data.PARTNER_COLLEGE,
            kind="college",
            city=self.city["name"],
            email_domains=["kit.edu.in"],
            join_code="KIT-PILOT-2026",
        )

    def build_story_cast(self) -> None:
        rows = []
        for i, (key, (role, name)) in enumerate(PERSONAS.items()):
            kw: dict = {"verification_level": 3 if role in ("mentor", "investor", "super_admin", "partner_admin") else 2}
            if key == "ravi":
                kw.update(college=data.PARTNER_COLLEGE, organisation=self.org, verification_level=1, visible_to_org=True)
            if key == "meenakshi":
                kw.update(organisation=self.org)
            if key in ("asha", "priya", "arjun"):
                kw.update(circuits_opt_in=True)
            if key in ("lakshmi", "vikram"):
                kw.update(open_intro_slots=5)
            rows.append(self.new_member(key, role, name, i, **kw))
        for m, key in zip(Member.objects.bulk_create(rows), PERSONAS):
            self.members[key] = m
        self.org.created_by = self.members["admin"]
        self.org.save(update_fields=["created_by"])

    def build_bulk_members(self) -> None:
        rows, kinds = [], []
        for i in range(N_FOUNDERS - 7):  # 7 founders already exist as story personas
            rows.append(self.new_member(None, "founder", self.person_name(), i, verification_level=self.rnd.choice([1, 2, 2, 3])))
            kinds.append("founder")
        for i in range(N_MENTORS - 1):
            rows.append(self.new_member(None, "mentor", self.person_name(), i, verification_level=3, open_intro_slots=3))
            kinds.append("mentor")
        for i in range(N_INVESTORS - 1):
            rows.append(self.new_member(None, "investor", self.person_name(), i, verification_level=3))
            kinds.append("investor")
        n_students = N_STUDENTS - 1
        for i in range(n_students):
            partner = i < 60  # a big cohort at the partner college so the dashboard has real numbers
            college = data.PARTNER_COLLEGE if partner else self.rnd.choice(data.OTHER_COLLEGES + data.TIER1_COLLEGES)
            minor = i % 50 == 7
            rows.append(
                self.new_member(
                    None,
                    "student",
                    self.person_name(),
                    i,
                    college=college,
                    is_minor=minor,
                    organisation=self.org if partner else None,
                    visible_to_org=partner and i % 3 == 0,
                    verification_level=1,
                )
            )
            kinds.append("student")
        self.bulk_students: list[Member] = []
        self.bulk_founders: list[Member] = []
        self.bulk_mentors: list[Member] = []
        self.bulk_investors: list[Member] = []
        for m, kind in zip(Member.objects.bulk_create(rows), kinds):
            getattr(self, f"bulk_{kind}s").append(m)

    def build_startups_and_jobs(self) -> None:
        sectors = list(data.SECTORS)
        story = [  # (key, name, sector, hiring, owner persona)
            ("vitrix", "Vitrix Biosciences", "biotech", False, "kavya"),
            ("quantora", "Quantora Systems", "deeptech", False, "rohan"),
            ("pixelwave", "Pixelwave Labs", "saas", True, "divya"),
            ("kaapikart", "Kaapi Kart", "d2c", False, "asha"),
            ("medha", "Medha Health", "healthtech", False, "priya"),
            ("suvidha", "Suvidha Logistics", "logistics", False, "arjun"),
            ("aqualytics", "Aqualytics", "cleantech", False, "sneha"),
        ]
        for key, name, sector, hiring, owner in story:
            self.startups[key] = self.make_startup(name, sector, hiring, domain=f"{name.lower().replace(' ', '')}.in")
            self.startups[key].claimed_by = self.members[owner]
            self.startups[key].claimed_at = timezone.now() - timedelta(days=30)
        # Pixelwave must be near the partner college (story 3): put it in Guindy.
        self.startups["pixelwave"].location = self.point(0)
        extra = {}
        claim_pool = list(self.bulk_founders)
        for i in range(N_STARTUPS - len(story)):
            sector = sectors[i % len(sectors)]
            name = f"{self.rnd.choice(data.NAME_A)}{self.rnd.choice(data.NAME_B)}".capitalize()
            s = self.make_startup(name, sector, hiring=self.rnd.random() < 0.45)
            if i < len(claim_pool):  # ~23 more claimed startups; the rest stay unclaimed (F3)
                s.claimed_by = claim_pool[i]
                s.claimed_at = timezone.now() - timedelta(days=self.rnd.randrange(3, 90))
            extra[f"s{i}"] = s
        self.startups.update(extra)
        created = Startup.objects.bulk_create(list(self.startups.values()))
        self.startups = dict(zip(self.startups, created))
        st_members, st_traits, jobs = [], [], []
        for key, s in self.startups.items():
            traits, job_caps, _ = data.SECTORS[s.sector]
            for t in traits[:3]:
                st_traits.append(StartupTrait(startup=s, trait=self.trait[t]))
            if s.claimed_by:
                st_members.append(StartupMember(startup=s, member=s.claimed_by, role="founder"))
            if s.hiring:
                for _ in range(1 if key != "pixelwave" else 0):
                    jobs.append(
                        (
                            Job(
                                startup=s,
                                title=self.rnd.choice(["Intern", "Associate", "Trainee"]) + f" – {self.cap[job_caps[0]].name}",
                                kind=self.rnd.choice(["internship", "internship", "part_time", "full_time"]),
                                stipend_min=(st := self.rnd.choice(data.STIPENDS))[0],
                                stipend_max=st[1],
                                location=s.address,
                                posted_by=s.claimed_by,
                            ),
                            job_caps[:3],
                        )
                    )
        StartupMember.objects.bulk_create(st_members)
        StartupTrait.objects.bulk_create(st_traits)
        self._save_jobs(jobs)

    def _save_jobs(self, jobs: list[tuple[Job, list[str]]]) -> None:
        saved = Job.objects.bulk_create([j for j, _ in jobs])
        JobCapability.objects.bulk_create(
            [
                JobCapability(job=j, capability=self.cap[c], required=i == 0)
                for j, (_, caps) in zip(saved, jobs)
                for i, c in enumerate(caps)
            ]
        )

    def build_stories(self) -> None:
        m = self.members
        # Story 1: biotech needs marketing; deep-tech marketer offers it. Different sectors, same buyer traits.
        self.add_needs_offers(m["kavya"], ["b2b-marketing"], ["biotech-lab", "clinical-research"])
        self.add_needs_offers(m["rohan"], ["fundraising"], ["b2b-marketing", "product-marketing"])
        for key, traits in (
            ("kavya", ["long-sales-cycle", "technical-buyers", "regulated-industry"]),
            ("rohan", ["long-sales-cycle", "technical-buyers", "deep-tech"]),
        ):
            self.member_traits_extra[key] = traits
        # Story 2: the circuit. Priya gives marketing to Asha, Arjun gives fundraising to Priya, Asha gives hiring to Arjun.
        self.add_needs_offers(m["asha"], ["brand-marketing"], ["recruiting"])
        self.add_needs_offers(m["priya"], ["fundraising"], ["brand-marketing"])
        self.add_needs_offers(m["arjun"], ["recruiting"], ["fundraising"])
        # Story 3: a tier-3 student with real proof of work, a nearby hiring startup, and weaker rival applicants.
        px = self.startups["pixelwave"]
        job = Job.objects.create(
            startup=px,
            title="Frontend Intern",
            kind="internship",
            description="Build screens in React with our designer.",
            stipend_min=10000,
            stipend_max=15000,
            location=px.address,
            posted_by=m["divya"],
        )
        JobCapability.objects.bulk_create(
            [
                JobCapability(job=job, capability=self.cap["frontend-dev"], required=True),
                JobCapability(job=job, capability=self.cap["ui-design"], required=False),
            ]
        )
        self.story_job = job
        self.skill_overrides["ravi"] = [("frontend-dev", 3, "https://github.com/ravi-kumar-demo/portfolio"), ("ui-design", 2, "")]
        rivals = [s for s in self.bulk_students if s.college in data.TIER1_COLLEGES][:4]
        for i, rival in enumerate(rivals):
            self.skill_overrides[rival.pk] = [("frontend-dev", 1, "")]
            Application.objects.create(job=job, student=rival, skill_match=round(0.3 + 0.05 * i, 2))
        self.add_needs_offers(m["ravi"], ["mentoring"], ["frontend-dev", "ui-design"])
        # Story 4: Sneha -> mentor Lakshmi -> investor Vikram. No direct Sneha-Vikram link.
        self.add_needs_offers(m["sneha"], ["investor-intros"], ["grants-funding"])
        self.add_needs_offers(m["vikram"], ["market-research"], ["investor-intros", "fundraising"])
        self.add_needs_offers(m["lakshmi"], [], ["mentoring", "investor-intros", "business-strategy"])
        self.fixed_connections = [("sneha", "lakshmi", 0.9), ("lakshmi", "vikram", 0.9)]
        # Story 5: the partner college cohort needs regulatory help; nobody in the organisation offers it.
        org_students = [s for s in self.bulk_students if s.organisation_id][:9]
        for s in org_students:
            self.add_needs_offers(s, ["regulatory-affairs"], [])
        for s in self.bulk_mentors[:2]:  # offered outside the organisation only
            self.add_needs_offers(s, [], ["regulatory-affairs"])

    def save_skills_traits(self) -> None:
        skills, traits = [], []
        everyone = list(self.members.items())
        for key, mem in everyone:
            for slug in self.member_traits_extra.get(key, []):
                traits.append(MemberTrait(member=mem, trait=self.trait[slug]))
        for s in self.bulk_students:
            picks = self.rnd.sample(data.STUDENT_SKILL_POOL, self.rnd.randint(2, 4))
            over = self.skill_overrides.get(s.pk)
            for slug, lvl, proof in over or [(p, self.rnd.randint(1, 2), "") for p in picks]:
                skills.append(MemberSkill(member=s, capability=self.cap[slug], level=lvl, proof_url=proof))
            for t in self.rnd.sample(data.STUDENT_TRAITS, 2):
                traits.append(MemberTrait(member=s, trait=self.trait[t]))
            if not over:
                self.add_needs_offers(s, self.rnd.sample(data.STUDENT_NEED_POOL, 1), [p for p, _ in zip(picks, range(2))])
        for slug, lvl, proof in self.skill_overrides["ravi"]:
            skills.append(MemberSkill(member=self.members["ravi"], capability=self.cap[slug], level=lvl, proof_url=proof))
        for t in ("student-friendly", "tier2-3-focus"):
            traits.append(MemberTrait(member=self.members["ravi"], trait=self.trait[t]))
        sectors = list(data.SECTORS)
        for i, f in enumerate(self.bulk_founders):
            sector_traits, _, f_needs = data.SECTORS[sectors[i % len(sectors)]]
            for t in sector_traits[:2]:
                traits.append(MemberTrait(member=f, trait=self.trait[t]))
            self.add_needs_offers(f, self.rnd.sample(f_needs, 1), self.rnd.sample(data.SECTORS[sectors[i % len(sectors)]][1], 1))
        for m in self.bulk_mentors + self.bulk_investors:
            self.add_needs_offers(
                m, [], self.rnd.sample(["mentoring", "fundraising", "business-strategy", "investor-intros", "pitch-coaching"], 2)
            )
        MemberSkill.objects.bulk_create(skills)
        MemberTrait.objects.bulk_create(traits)

    def save_needs_offers(self) -> None:
        embedder = get_embedder()
        texts = [t for _, _, t in self.needs] + [t for _, _, t in self.offers]
        vecs = embedder.embed(texts)
        nv, ov = vecs[: len(self.needs)], vecs[len(self.needs) :]
        seen: set[tuple] = set()
        needs, offers = [], []
        for (m, slug, text), v in zip(self.needs, nv):
            if ("n", m.pk, slug) not in seen:
                seen.add(("n", m.pk, slug))
                needs.append(Need(member=m, capability=self.cap[slug], description=text, embedding=v))
        for (m, slug, text), v in zip(self.offers, ov):
            if ("o", m.pk, slug) not in seen:
                seen.add(("o", m.pk, slug))
                offers.append(Offer(member=m, capability=self.cap[slug], description=text, embedding=v))
        Need.objects.bulk_create(needs)
        Offer.objects.bulk_create(offers)

    def build_connections(self) -> None:
        pairs: dict[tuple[int, int], tuple[float, str]] = {}
        for a, b, strength in self.fixed_connections:
            x, y = sorted((self.members[a].pk, self.members[b].pk))
            pairs[(x, y)] = (strength, "story")
        everyone = [
            m
            for m in Member.objects.exclude(role__in=["super_admin", "partner_admin"])
            if m.pk not in {self.members["sneha"].pk, self.members["vikram"].pk}
        ]
        for m in everyone:
            for other in self.rnd.sample(everyone, 3):
                if other.pk != m.pk:
                    x, y = sorted((m.pk, other.pk))
                    pairs.setdefault((x, y), (round(self.rnd.uniform(0.3, 0.8), 2), "seed"))
        Connection.objects.bulk_create(
            [Connection(member_a_id=a, member_b_id=b, strength=s, source=src) for (a, b), (s, src) in pairs.items()]
        )

    def build_consents(self) -> None:
        now = timezone.now()
        Consent.objects.bulk_create([Consent(member=m, policy_version="2026-01", accepted_at=now) for m in Member.objects.all()])

    # -- social (F15-F17): build logs with drawn project screenshots, replies, follows, requests, chats -------------
    def _image(self, owner: Member, n: int, scene: str) -> MediaUpload:
        """A drawn 'screenshot' stored through the storage provider (same two sizes the upload flow produces)."""
        path = f"post/{owner.pk}/seed{n}"
        png = mockups.render(scene)
        from apps.social import media

        variants, (w, h) = media._process(png)
        store = get_storage()
        for width, blob in variants.items():
            store.put("posts", f"{path}/{media.VARIANTS[width]}", blob, "image/webp")
        return MediaUpload.objects.create(owner=owner, purpose="post", path=path, status="ready", width=w, height=h)

    def _post(self, author: Member, body: str, visibility: str, hours_ago: float, images=(), tags=(), link: str = "") -> Post:
        post = Post.objects.create(author=author, body=body, visibility=visibility, link=link)
        Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))
        post.capabilities.set([self.cap[t] for t in tags])
        for i, (scene, alt) in enumerate(images):
            up = self._image(author, self.image_n, scene)
            self.image_n += 1
            PostMedia.objects.create(post=post, upload=up, alt_text=alt, order=i)
        return post

    def build_social(self) -> None:
        m, rnd = self.members, self.rnd
        self.image_n = 0
        feature = [
            (
                "asha",
                "Week 6 of the diagnostics dashboard: sample turnaround per lab, now with a late-sample flag. Looking for a marketer who has sold to labs.",
                "everyone",
                3,
                [
                    (
                        "turnaround_tracker",
                        "Dashboard: 1,284 samples this week, 91.4% on time, 37 late, a bar chart of daily turnaround against a 6 hour limit, and a table of five labs",
                    )
                ],
                ["brand-marketing"],
            ),
            (
                "priya",
                "Rebuilt our investor update as a single page. Three numbers, one ask. Fundraising is mostly editing.",
                "connections",
                7,
                [
                    (
                        "investor_update",
                        "Investor update page: MRR of ₹4.8L, 14 months of runway, 11 hospitals live, a revenue line rising from April to September, and the ask for two intros",
                    )
                ],
                ["fundraising"],
            ),
            (
                "arjun",
                "Our hiring board after switching to two-day trial projects. Fewer interviews, better hires.",
                "everyone",
                21,
                [
                    (
                        "hiring_board",
                        "Hiring board with three columns, trial sent, in progress and reviewed, and a candidate with a trial task on each card",
                    )
                ],
                ["recruiting"],
            ),
            (
                "kavya",
                "Assay run 14: signal-to-noise finally above 10. Posting the plate reader chart before I lose the settings.",
                "everyone",
                30,
                [
                    (
                        "assay_run",
                        "Plate reader chart of fluorescence over 60 minutes, sample rising to 9,400 against a flat blank, signal to noise 10.4",
                    )
                ],
                ["clinical-research"],
            ),
            (
                "divya",
                "We are hiring a frontend intern at Pixelwave. React, a designer next to you, real users by week three.",
                "everyone",
                5,
                [
                    (
                        "onboarding_phone",
                        "Phone screen, Set up your studio, with two of four steps done and Pick your first campaign next",
                    )
                ],
                ["frontend-dev", "ui-design"],
            ),
            (
                "ravi",
                "Built a React Native attendance app for our department. First version works offline. Code is on GitHub, feedback welcome.",
                "everyone",
                2,
                [
                    (
                        "attendance_phone",
                        "Attendance app showing today's four classes, two present, one absent, one not marked, and an offline banner",
                    ),
                    (
                        "sync_code",
                        "Code editor showing the function that syncs saved attendance marks when the phone is back online",
                    ),
                ],
                ["frontend-dev"],
            ),
            (
                "lakshmi",
                "Office hours this Thursday at the incubator. Bring one question about your first customer, not your whole deck.",
                "everyone",
                26,
                [],
                ["mentoring"],
            ),
            (
                "rohan",
                "Deep-tech sales cycles are 9 months. Writing down what moved a deal forward each month.",
                "everyone",
                40,
                [("deal_log", "Deal log of six institutional deals by stage, from intro to won, with values in rupees")],
                ["b2b-marketing"],
            ),
            (
                "sneha",
                "Investor intros are warmer when a mentor says one specific thing about you. Grateful for Dr. Lakshmi's.",
                "connections",
                12,
                [],
                ["investor-intros"],
            ),
        ]
        # Roles were all created at seed time; spread them over the week so Pulse shows a believable mix.
        jobs = list(Job.objects.order_by("pk"))
        for job in jobs:
            Job.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(hours=rnd.randint(1, 160)))
        posts: dict[str, Post] = {}
        for key, body, vis, hrs, imgs, tags in feature:
            posts[key] = self._post(m[key], body, vis, hrs, imgs, tags)
        # Everyday posts from partner-college students (organisation-only for under-18s) and other builders.
        topics = [
            (
                "Finished the sensor wiring for our Arduino soil-moisture project. The pump switches on below 35%.",
                ("serial_monitor", "Serial monitor log of soil moisture readings; the pump turns on when moisture falls to 34%"),
                ["embedded-systems"],
            ),
            (
                "Our hackathon team shipped a bus-timing app in 24 hours. Slept 3.",
                ("bus_app", "App screen listing the next five buses at Hostel Gate with minutes to arrival"),
                ["frontend-dev"],
            ),
            (
                "Tried Figma for the first time. The auto layout clicked on day two.",
                (
                    "figma_frames",
                    "Figma window with a profile card selected and its auto layout settings: vertical, gap 8, padding 16",
                ),
                ["ui-design"],
            ),
            (
                "Learning SQL by cleaning our college library's CSV. 400 duplicate rows so far.",
                ("dedupe_sql", "SQL query grouping books by ISBN and a result listing ISBNs with duplicate copies"),
                ["data-analysis"],
            ),
            (
                "Wrote my first cold email to a startup. Got a reply in an hour.",
                ("cold_email", "Email reply from a startup founder asking for a 20 minute call tomorrow at 4 pm"),
                ["b2b-marketing"],
            ),
        ]
        org_students = [s for s in self.bulk_students if s.organisation_id and s.pk != m["ravi"].pk]
        others = [s for s in self.bulk_students if not s.organisation_id] + self.bulk_founders
        authors = rnd.sample(org_students, 14) + rnd.sample(others, 12)
        for i, who in enumerate(authors):
            text, shot, tags = topics[i % len(topics)]
            vis = (
                "organisation"
                if who.is_minor or (who.organisation_id and i % 3 == 0)
                else rnd.choice(["everyone", "connections"])
            )
            if who.is_minor or (vis == "organisation" and not who.organisation_id):
                vis = "organisation" if who.organisation_id else "connections"
            imgs = [shot] if i % 2 == 0 else []
            tags = [t for t in tags if t in self.cap][:3]
            self._post(who, text, vis, rnd.choice([1, 4, 9, 20, 30, 50, 90, 120]), imgs, tags)
        # A thread, a few reactions and follows.
        everyone = list(Member.objects.exclude(role__in=["super_admin", "partner_admin"]).filter(is_minor=False).order_by("pk"))
        for key in ("asha", "ravi", "divya"):
            p = posts[key]
            top = Reply.objects.create(
                post=p,
                author=rnd.choice([x for x in everyone if x.pk != p.author_id]),
                body=rnd.choice(
                    [
                        "How did you handle offline sync?",
                        "This is useful. What did you use for the chart?",
                        "Would love to try this.",
                    ]
                ),
            )
            Reply.objects.create(post=p, author=p.author, body="Thanks! Happy to share how, message me.", parent=top)
        reactions = []
        for p in Post.objects.filter(visibility="everyone"):
            for who in rnd.sample(everyone, 3):
                if who.pk != p.author_id:
                    reactions.append(
                        Reaction(post=p, member=who, kind=rnd.choice(["helpful", "helpful", "intro_me", "lets_talk"]))
                    )
        Reaction.objects.bulk_create(reactions, ignore_conflicts=True)
        hiring = list(Startup.objects.filter(hiring=True).order_by("pk")[:6])
        follows = [Follow(member=m["ravi"], startup=s) for s in [self.startups["pixelwave"], *hiring[:3]]]
        follows += [Follow(member=s, startup=rnd.choice(hiring)) for s in rnd.sample(org_students, 10)]
        Follow.objects.bulk_create(follows, ignore_conflicts=True)
        # Connection requests and chats.
        ConnectionRequest.objects.create(
            sender=m["ravi"], recipient=m["lakshmi"], note="I built an attendance app and need a mentor for my first internship."
        )
        ConnectionRequest.objects.create(
            sender=rnd.choice(org_students), recipient=m["ravi"], note="Same department, loved your attendance app."
        )
        self._chat(
            m["asha"],
            m["arjun"],
            ["Saw your hiring board. How long is a trial project?", "Two days, paid. I will send the template."],
            active=True,
        )
        self._chat(
            m["sneha"],
            m["lakshmi"],
            ["Thank you for the intro note.", "Anytime. Send me your one-pager before Thursday."],
            active=True,
        )
        self._chat(
            m["ravi"], m["divya"], ["Hi, I am applying to the frontend internship. Happy to share my portfolio."], active=False
        )

    def _chat(self, a: Member, b: Member, lines: list[str], active: bool) -> None:
        x, y = sorted((a.pk, b.pk))
        conv = Conversation.objects.create(member_a_id=x, member_b_id=y, started_by=a, status="active" if active else "request")
        now = timezone.now()
        for i, line in enumerate(lines):
            msg = Message.objects.create(conversation=conv, sender=a if i % 2 == 0 else b, body=line)
            Message.objects.filter(pk=msg.pk).update(created_at=now - timedelta(minutes=30 * (len(lines) - i)))
        conv.last_message_at = now - timedelta(minutes=30)
        conv.save(update_fields=["last_message_at"])


def run(city: dict) -> dict:
    return Seeder(city).run()
