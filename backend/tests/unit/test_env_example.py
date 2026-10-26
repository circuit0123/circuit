"""`.env.example` and the settings agree exactly: every variable the app reads is documented, and nothing documented is ignored."""

import re

from django.conf import settings

from circuit.config import Config

EXAMPLE = (settings.BASE_DIR.parent / ".env.example").read_text()
# Read straight from the environment by the production container, not by Config (gunicorn.py, the Dockerfile, core/monitoring.py)
READ_ELSEWHERE = {"PORT", "WEB_CONCURRENCY", "GUNICORN_THREADS", "FASTEMBED_CACHE_PATH", "GOOGLE_CLOUD_PROJECT"}


def _documented() -> set[str]:
    keys = set(re.findall(r"^#?\s?([A-Z][A-Z0-9_]*)=", EXAMPLE, flags=re.MULTILINE))
    return {k for k in keys if not k.startswith("NEXT_PUBLIC_")}  # the frontends' own variables


def test_every_config_field_is_in_env_example():
    fields = {name.upper() for name in Config.model_fields}
    assert not fields - _documented(), f"add to .env.example: {sorted(fields - _documented())}"


def test_every_documented_variable_is_read_by_something():
    fields = {name.upper() for name in Config.model_fields}
    assert not _documented() - fields - READ_ELSEWHERE, f"in .env.example but not read: {sorted(_documented() - fields - READ_ELSEWHERE)}"
