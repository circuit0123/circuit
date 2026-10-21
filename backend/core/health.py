import structlog
from django.conf import settings
from django.db import connection
from ninja import Router, Schema, Status

log = structlog.get_logger("health")
router = Router()


class Health(Schema):
    status: str


class DepStatus(Schema):
    status: str
    postgres: str
    redis: str
    jwks: str


@router.get("", response=Health, summary="Liveness", description="Process is up. Touches no dependencies.", auth=None)
def health(request):
    return {"status": "ok"}


@router.get(
    "/deps",
    response={200: DepStatus, 503: DepStatus},
    summary="Dependency health",
    description="Checks Postgres, Redis and the Supabase JWKS (skipped when SUPABASE_URL is unset). "
    "Redis down is degraded, not failed, because Postgres is the source of truth.",
    auth=None,
)
def deps(request):
    from core.cache import get_cache

    pg = "ok"
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        pg = "down"
    redis_state = "ok" if get_cache().ping() else "down"
    jwks = "skipped"
    if settings.SUPABASE_URL:
        from core.auth import jwks_reachable

        jwks = "ok" if jwks_reachable() else "down"
    overall = "ok" if pg == "ok" and jwks != "down" else "fail"
    if overall == "ok" and redis_state == "down":
        overall = "degraded"
    body = {"status": overall, "postgres": pg, "redis": redis_state, "jwks": jwks}
    return Status(503 if overall == "fail" else 200, body)
