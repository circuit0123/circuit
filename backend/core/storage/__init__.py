"""Private file storage behind one interface: Supabase Storage in real use, local files in dev, memory in tests.

Buckets are private. The browser uploads to a short-lived signed URL we hand out and reads through signed URLs, so
nothing is public and nothing needs a storage RLS policy. The service-role key is used only here, in the backend.
Every Supabase call has a timeout and retries with backoff.
"""

import time
from pathlib import Path
from typing import Protocol

import httpx
import structlog
from django.conf import settings

from core.errors import ServiceUnavailable

log = structlog.get_logger("storage")
SIGNED_READ_SECONDS = 3600
TIMEOUT = 5.0
RETRIES = 3


class StorageProvider(Protocol):
    def signed_upload_url(self, bucket: str, path: str) -> str: ...
    def get(self, bucket: str, path: str) -> bytes: ...
    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None: ...
    def delete(self, bucket: str, paths: list[str]) -> None: ...
    def signed_urls(self, bucket: str, paths: list[str]) -> dict[str, str]: ...


class MemoryStorage:
    """Tests: files live in a dict, URLs are fake but stable."""

    def __init__(self) -> None:
        self.files: dict[tuple[str, str], bytes] = {}

    def signed_upload_url(self, bucket: str, path: str) -> str:
        return f"https://storage.test/upload/{bucket}/{path}?token=t"

    def get(self, bucket: str, path: str) -> bytes:
        try:
            return self.files[(bucket, path)]
        except KeyError:
            raise FileNotFoundError(path) from None

    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        self.files[(bucket, path)] = data

    def delete(self, bucket: str, paths: list[str]) -> None:
        for p in paths:
            self.files.pop((bucket, p), None)

    def signed_urls(self, bucket: str, paths: list[str]) -> dict[str, str]:
        return {p: f"https://storage.test/read/{bucket}/{p}?token=t" for p in paths}


class LocalStorage:
    """Dev: files under MEDIA_ROOT, read through the dev-only /api/media/dev route. Browser uploads need Supabase."""

    def _file(self, bucket: str, path: str) -> Path:
        root = Path(settings.MEDIA_ROOT).resolve()
        f = (root / bucket / path).resolve()
        if root not in f.parents:
            raise ValueError("path escapes the media root")
        return f

    def signed_upload_url(self, bucket: str, path: str) -> str:
        raise ServiceUnavailable("Uploads from the browser need STORAGE_PROVIDER=supabase", "uploads_unavailable")

    def get(self, bucket: str, path: str) -> bytes:
        return self._file(bucket, path).read_bytes()

    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        f = self._file(bucket, path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)

    def delete(self, bucket: str, paths: list[str]) -> None:
        for p in paths:
            self._file(bucket, p).unlink(missing_ok=True)

    def signed_urls(self, bucket: str, paths: list[str]) -> dict[str, str]:
        return {p: f"{settings.API_URL}/api/media/dev/{bucket}/{p}" for p in paths}


class SupabaseStorage:
    def _call(self, method: str, url: str, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}", "apikey": settings.SUPABASE_SERVICE_ROLE_KEY}
        last: Exception | None = None
        for attempt in range(RETRIES):
            try:
                r = httpx.request(
                    method, f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{url}", headers=headers, timeout=TIMEOUT, **kw
                )
                if r.status_code < 500:
                    return r
                last = RuntimeError(f"storage {r.status_code}")
            except httpx.HTTPError as e:
                last = e
            time.sleep(0.2 * 2**attempt)
        log.warning("storage_unavailable", error=type(last).__name__)
        raise ServiceUnavailable("File storage is not reachable right now. Try again in a minute.", "storage_unavailable")

    def signed_upload_url(self, bucket: str, path: str) -> str:
        r = self._call("POST", f"/object/upload/sign/{bucket}/{path}")
        r.raise_for_status()
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{r.json()['url']}"

    def get(self, bucket: str, path: str) -> bytes:
        r = self._call("GET", f"/object/{bucket}/{path}")
        if r.status_code == 404:
            raise FileNotFoundError(path)
        r.raise_for_status()
        return r.content

    def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        r = self._call(
            "POST", f"/object/{bucket}/{path}", content=data, headers={"Content-Type": content_type, "x-upsert": "true"}
        )
        r.raise_for_status()

    def delete(self, bucket: str, paths: list[str]) -> None:
        if paths:
            self._call("DELETE", f"/object/{bucket}", json={"prefixes": paths}).raise_for_status()

    def signed_urls(self, bucket: str, paths: list[str]) -> dict[str, str]:
        if not paths:
            return {}
        r = self._call("POST", f"/object/sign/{bucket}", json={"expiresIn": SIGNED_READ_SECONDS, "paths": paths})
        r.raise_for_status()
        base = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1"
        return {row["path"]: f"{base}{row['signedURL']}" for row in r.json() if row.get("signedURL")}


_provider: StorageProvider | None = None


def get_storage() -> StorageProvider:
    global _provider
    if _provider is None:
        _provider = SupabaseStorage() if settings.STORAGE_PROVIDER == "supabase" else LocalStorage()
    return _provider


def set_storage(provider: StorageProvider | None) -> None:
    global _provider
    _provider = provider
