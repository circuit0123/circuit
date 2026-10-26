"""Beta-mix load test: `python -m core.loadtest --url ... --tokens file --users 50,200 --seconds 60` (or `make load-test`).

Plain httpx + asyncio, no Django. Each simulated user signs in with one of the tokens and loops through what a beta member does:
config and me, Home, Discover, Map, a job page and apply, Inbox, send a message. It reports p50 / p95 / error rate per endpoint
against PRODUCTION.md §9 (300 ms for cached reads, 800 ms for the rest). It refuses to run against production.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import httpx

CACHED_TARGET_MS = 300
OTHER_TARGET_MS = 800
# Answers that are normal for the test, not errors: the first message may find an old request (409) or a hidden member (404)
EXPECTED = {"POST /api/conversations": {201, 404, 409}}
CACHED = {"GET /api/config", "GET /api/matches"}  # served from Redis or precomputed rows
BOX = 0.1  # map box half-size in degrees; a phone shows about this much


@dataclass
class Sample:
    ms: float
    status: int  # 0 = connection error or timeout


@dataclass
class Stats:
    samples: list[Sample] = field(default_factory=list)

    def add(self, ms: float, status: int) -> None:
        self.samples.append(Sample(ms, status))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))  # nearest rank
    return ordered[max(1, rank) - 1]


def summarise(stats: dict[str, Stats]) -> list[dict]:
    rows = []
    for name, st in sorted(stats.items()):
        ms = [s.ms for s in st.samples]
        n = len(st.samples)
        limited = sum(1 for s in st.samples if s.status == 429)
        ok = EXPECTED.get(name, set())
        errors = sum(
            1
            for s in st.samples
            if s.status not in ok and (s.status == 0 or s.status >= 500 or (400 <= s.status < 500 and s.status != 429))
        )
        target = CACHED_TARGET_MS if name in CACHED else OTHER_TARGET_MS
        p95 = percentile(ms, 95)
        rows.append(
            {
                "endpoint": name,
                "requests": n,
                "p50_ms": round(percentile(ms, 50)),
                "p95_ms": round(p95),
                "target_ms": target,
                "error_pct": round(100 * errors / n, 2) if n else 0.0,
                "rate_limited": limited,
                "statuses": {
                    str(k): v for k, v in sorted(Counter(x.status for x in st.samples).items()) if k != 200 and k != 204
                },
                "pass": bool(n) and p95 < target and errors == 0,
            }
        )
    return rows


def render(users: int, seconds: float, rows: list[dict]) -> str:
    total = sum(r["requests"] for r in rows)
    out = [f"\n== {users} concurrent users, {seconds:.0f}s, {total} requests ({total / seconds:.1f}/s) =="]
    out.append(f"{'endpoint':42} {'n':>6} {'p50':>6} {'p95':>6} {'target':>6} {'err%':>6} {'429':>5}  result")
    for r in rows:
        out.append(
            f"{r['endpoint']:42} {r['requests']:>6} {r['p50_ms']:>6} {r['p95_ms']:>6} {r['target_ms']:>6} "
            f"{r['error_pct']:>6} {r['rate_limited']:>5}  {'PASS' if r['pass'] else 'FAIL'}"
        )
    odd = [f"  {r['endpoint']}: {r['statuses']}" for r in rows if r["statuses"]]
    if odd:
        out.append("Other statuses (0 = connection error or timeout):\n" + "\n".join(odd))
    return "\n".join(out)


async def check_not_production(client: httpx.AsyncClient, url: str) -> str | None:
    """Return a reason to stop, or None when the target is safe. If we cannot tell what it is, we do not run."""
    try:
        r = await client.get(f"{url}/api/config")
        env = r.json()["env"]
    except Exception as exc:  # any failure means "cannot tell"
        return (
            f"could not read {url}/api/config ({type(exc).__name__}); not running a load test against something I cannot identify"
        )
    if env == "production":
        return "that is the PRODUCTION environment. Load tests run on local or staging only."
    return None


class User:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        token: str,
        stats: dict[str, Stats],
        rnd: random.Random,
        centre: tuple[float, float],
    ):
        self.c, self.url, self.rnd, self.stats, self.centre = client, url, rnd, stats, centre
        self.h = {"Authorization": f"Bearer {token}"}
        self.job_id: int | None = None
        self.conversation_id: int | None = None
        self.peer: int | None = None  # someone from my matches, to start a first conversation with
        self.started = False
        self.role = ""

    async def call(self, method: str, path: str, label: str | None = None, **kw) -> httpx.Response | None:
        name = f"{method} {label or path.split('?')[0]}"
        start = time.perf_counter()
        try:
            r = await self.c.request(method, f"{self.url}{path}", headers=self.h, **kw)
            self.stats.setdefault(name, Stats()).add((time.perf_counter() - start) * 1000, r.status_code)
            return r
        except httpx.HTTPError:
            self.stats.setdefault(name, Stats()).add((time.perf_counter() - start) * 1000, 0)
            return None

    async def pause(self) -> None:
        await asyncio.sleep(self.rnd.uniform(0.5, 2.0))

    async def json(self, r: httpx.Response | None):
        try:
            return r.json() if r is not None and r.status_code == 200 else None
        except ValueError:
            return None

    async def session(self) -> None:
        await self.call("GET", "/api/config")
        me = await self.json(await self.call("GET", "/api/me"))
        self.role = (me or {}).get("role", "")
        await self.pause()

    async def home(self) -> None:
        for p in ("/api/drop/today", "/api/livewire", "/api/pulse?limit=20"):
            await self.call("GET", p)
        await self.pause()

    async def discover(self) -> None:
        matches = await self.json(await self.call("GET", "/api/matches?limit=20"))
        people = (matches or {}).get("items") or []
        if people and self.peer is None:
            self.peer = people[0]["candidate_id"]
        jobs = await self.json(await self.call("GET", "/api/jobs?limit=20"))
        await self.call("GET", "/api/startups/nearby")
        await self.call("GET", f"/api/search?q={self.rnd.choice(['ai', 'design', 'data', 'market', 'app'])}")
        items = (jobs or {}).get("items") or []
        if items:
            self.job_id = self.rnd.choice(items)["id"]
        await self.pause()

    async def map(self) -> None:
        lat, lng = self.centre
        a = self.rnd.uniform(-BOX / 2, BOX / 2)
        await self.call(
            "GET",
            f"/api/startups/map?min_lng={lng - BOX + a}&min_lat={lat - BOX + a}&max_lng={lng + BOX + a}&max_lat={lat + BOX + a}",
            label="/api/startups/map",
        )
        await self.pause()

    async def job(self) -> None:
        if self.job_id is None:
            return
        await self.call("GET", f"/api/jobs/{self.job_id}", label="/api/jobs/{id}")
        if self.role == "student":
            await self.call("POST", f"/api/jobs/{self.job_id}/apply", label="/api/jobs/{id}/apply")
        await self.pause()

    async def inbox(self) -> None:
        convs = await self.json(await self.call("GET", "/api/conversations?folder=chats"))
        await self.call("GET", "/api/conversations/unread-count")
        rows = convs if isinstance(convs, list) else (convs or {}).get("items") or []
        if rows:
            self.conversation_id = rows[0]["id"]
        await self.pause()

    async def message(self) -> None:
        if self.conversation_id is None:
            if (
                self.peer is not None and not self.started
            ):  # a member with no chats yet: say hello once (a request allows one message)
                self.started = True
                await self.call("POST", "/api/conversations", json={"member_id": self.peer, "body": "load test hello"})
                await self.pause()
            return
        await self.call(
            "POST",
            f"/api/conversations/{self.conversation_id}/messages",
            label="/api/conversations/{id}/messages",
            json={"body": "load test"},
        )
        await self.pause()

    async def run(self, stop_at: float) -> None:
        await self.session()
        steps = [self.home, self.discover, self.map, self.job, self.inbox, self.message]
        while time.monotonic() < stop_at:
            for step in steps:
                if time.monotonic() >= stop_at:
                    return
                await step()


async def run_level(
    url: str, tokens: list[str], users: int, seconds: float, seed: int, centre: tuple[float, float]
) -> list[dict]:
    stats: dict[str, Stats] = {}
    limits = httpx.Limits(max_connections=users + 10, max_keepalive_connections=users + 10)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        stop_at = time.monotonic() + seconds
        crowd = [User(client, url, tokens[i % len(tokens)], stats, random.Random(seed + i), centre) for i in range(users)]
        await asyncio.gather(*(u.run(stop_at) for u in crowd))
    return summarise(stats)


async def main_async(args: argparse.Namespace) -> int:
    url = args.url.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        reason = await check_not_production(client, url)
    if reason:
        print(f"REFUSING: {reason}", file=sys.stderr)
        return 2
    tokens = [t.strip() for t in Path(args.tokens).read_text().splitlines() if t.strip()]
    if not tokens:
        print("REFUSING: the token file is empty", file=sys.stderr)
        return 2
    results: dict[str, list[dict]] = {}
    failed = False
    for users in [int(u) for u in args.users.split(",")]:
        rows = await run_level(url, tokens, users, args.seconds, args.seed, (args.lat, args.lng))
        print(render(users, args.seconds, rows))
        results[str(users)] = rows
        failed = failed or not rows or any(not r["pass"] for r in rows)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
    print("\nRESULT:", "FAIL (some endpoint is over its PRODUCTION.md §9 target or has errors)" if failed else "PASS")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument("--tokens", required=True, help="file with one bearer token per line")
    p.add_argument("--users", default="50,200", help="comma-separated concurrent user levels")
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--lat", type=float, required=True, help="seed city centre (SEED_CITY_LAT)")
    p.add_argument("--lng", type=float, required=True, help="seed city centre (SEED_CITY_LNG)")
    p.add_argument("--json", help="also write the results to this file")
    return asyncio.run(main_async(p.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
