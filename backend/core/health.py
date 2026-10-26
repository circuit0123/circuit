import structlog
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from ninja import Router, Schema, Status

log = structlog.get_logger("health")
router = Router()


class ProbeMiddleware:
    """The two addresses the platform asks about, answered before anything else can get in the way.

    /health  "is the process up?"  Touches nothing, so it can only fail if the process is broken. Cloud Run uses it to decide
             whether to restart an instance: if it also checked Postgres, a database outage would make Cloud Run restart every
             healthy instance in a loop, which turns a blip into a long outage.
    /ready   "can it do its job?"  Postgres must answer (503 if not). Redis down is only a warning: Postgres is the source of
             truth and the app reads from it when the cache is away. Used by `make smoke` and by uptime monitors, never by restarts.

    Being first in MIDDLEWARE means they work with any Host header and over plain HTTP (the platform's probes send neither the
    real host nor https), and that a probe every few seconds does not fill the request log.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in ("GET", "HEAD"):
            if request.path == "/health":
                return self._json({"status": "ok"}, 200)
            if request.path == "/ready":
                return self.ready()
        return self.get_response(request)

    @staticmethod
    def _json(body: dict, status: int) -> JsonResponse:
        response = JsonResponse(body, status=status)
        response["Cache-Control"] = "no-store"
        return response

    def ready(self) -> JsonResponse:
        from core.cache import get_cache

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception as exc:
            connection.close()  # drop the broken connection so the next probe starts clean
            log.error("ready.failed", postgres="down", error=type(exc).__name__)
            return self._json({"status": "fail", "postgres": "down"}, 503)
        if not get_cache().ping():
            log.warning("ready.degraded", redis="down", note="reading from Postgres instead")
            return self._json({"status": "degraded", "postgres": "ok", "redis": "down"}, 200)
        return self._json({"status": "ok", "postgres": "ok", "redis": "ok"}, 200)


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
