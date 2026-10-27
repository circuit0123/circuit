"""Address -> (lat, lng) through OpenStreetMap Nominatim, for the one-off startup load.

One request per second, a User-Agent with our support email, a timeout and retries. Answers are cached in a local json file so
re-running the load never asks again. A network failure is not cached (the next run tries again); "no result" is.
"""

import json
import math
import time
from pathlib import Path

import httpx
from django.conf import settings

URL = "https://nominatim.openstreetmap.org/search"
CACHE_FILE = Path(settings.BASE_DIR) / "data" / "geocode_cache.json"
MAX_KM_FROM_CITY = 50  # a hit further away than this is a wrong match, not a pin


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = a, b
    h = (
        math.sin(math.radians(la2 - la1) / 2) ** 2
        + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    )
    return 12742 * math.asin(math.sqrt(h))


class Nominatim:
    def __init__(self, cache_file: Path = CACHE_FILE, tries: int = 3, pause: float = 1.0):
        if settings.SUPPORT_EMAIL.endswith("@example.com"):  # Nominatim refuses (403) a placeholder contact
            raise ValueError(
                "Set SUPPORT_EMAIL in .env to a real address: OpenStreetMap's Nominatim requires a contact in the User-Agent."
            )
        self.cache_file, self.tries, self.pause = cache_file, tries, pause
        self.cache: dict[str, list[float] | None] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        self.stats = {"hits": 0, "misses": 0, "cached": 0, "errors": 0}
        self._last = 0.0

    def lookup(self, address: str) -> tuple[float, float] | None:
        if address in self.cache:
            self.stats["cached"] += 1
            hit = self.cache[address]
        else:
            try:
                hit = self._fetch(address)
            except httpx.HTTPError:
                self.stats["errors"] += 1
                return None
            self.cache[address] = hit
            self._save()
        return (hit[0], hit[1]) if hit else None

    def _fetch(self, address: str) -> list[float] | None:
        headers = {"User-Agent": f"Circuit startup loader ({settings.SUPPORT_EMAIL})"}
        params = {"q": address, "format": "jsonv2", "limit": "1", "countrycodes": "in"}
        for attempt in range(self.tries):
            time.sleep(max(0.0, self.pause - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            try:
                resp = httpx.get(URL, params=params, headers=headers, timeout=10)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError("busy", request=resp.request, response=resp)
                rows = resp.raise_for_status().json()
                return [float(rows[0]["lat"]), float(rows[0]["lon"])] if rows else None
            except httpx.HTTPError as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in (429, 500, 502, 503, 504)
                if attempt == self.tries - 1 or not retryable:  # a 403/400 will not get better by asking again
                    raise
                time.sleep(2**attempt)
        return None

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, indent=1, sort_keys=True))
