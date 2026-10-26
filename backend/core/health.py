import structlog
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from ninja import Router, Schema, Status

from apps.accounts.models import Role
from core.auth import current_member
from core.permissions import require_role

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
        if not get_cache().configured:
            return self._json({"status": "ok", "postgres": "ok", "redis": "not_configured"}, 200)
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
    cache = get_cache()
    redis_state = "not_configured" if not cache.configured else "ok" if cache.ping() else "down"
    jwks = "skipped"
    if settings.SUPABASE_URL:
        from core.auth import jwks_reachable

        jwks = "ok" if jwks_reachable() else "down"
    overall = "ok" if pg == "ok" and jwks != "down" else "fail"
    if overall == "ok" and redis_state == "down":
        overall = "degraded"
    body = {"status": overall, "postgres": pg, "redis": redis_state, "jwks": jwks}
    return Status(503 if overall == "fail" else 200, body)


class JobOut(Schema):
    name: str
    interval_minutes: int
    last_status: str  # running | ok | skipped | failed | "" (never ran)
    last_started_at: str | None
    last_finished_at: str | None
    last_success_at: str | None
    last_error: str  # exception class + short scrubbed message; "" after a success
    overdue: bool  # no success for twice the interval
    reason: str


class JobsHealth(Schema):
    status: str  # ok | overdue
    overdue: int
    jobs: list[JobOut]


@router.get(
    "/jobs",
    response=JobsHealth,
    summary="Scheduled job health (super admins only)",
    description="Each scheduled job's last result and whether it is overdue (no success for twice its interval). "
    "The same check runs every 5 minutes as `check_jobs`, which logs `job.overdue` for the alert.",
    include_in_schema=False,  # an operator endpoint, not part of what the app's generated client or the frozen contract carries
)
def jobs_health(request: HttpRequest):
    from core import jobhealth

    require_role(current_member(request), Role.SUPER_ADMIN)
    rows = jobhealth.status()
    late = sum(1 for r in rows if r.overdue)

    def iso(value):
        return value.isoformat() if value else None

    return {
        "status": "overdue" if late else "ok",
        "overdue": late,
        "jobs": [
            {
                "name": r.name,
                "interval_minutes": r.interval_minutes,
                "last_status": r.last_status,
                "last_started_at": iso(r.last_started_at),
                "last_finished_at": iso(r.last_finished_at),
                "last_success_at": iso(r.last_success_at),
                "last_error": r.last_error,
                "overdue": r.overdue,
                "reason": r.reason,
            }
            for r in rows
        ],
    }
