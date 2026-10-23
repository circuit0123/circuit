from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.jobs.api import router as jobs_router
from apps.matching.api import router as matching_router
from apps.notifications.api import router as notifications_router
from apps.organisations.api import router as organisations_router
from apps.startups.api import router as startups_router
from core.auth import SupabaseAuth
from core.demo import router as demo_router
from core.errors import install_handlers
from core.health import router as health_router

api = NinjaAPI(
    title="Circuit API",
    version="1.0.0",
    description="Circuit backend. Errors always use {error: {code, message, details}}; lists use {items, count, next_offset}.",
    openapi_url=None if settings.ENV == "production" else "/openapi.json",  # no public API map in production
    docs_url=None if settings.ENV == "production" else "/docs",
    auth=SupabaseAuth(),  # default for every endpoint; public ones opt out with auth=None
)
install_handlers(api)
api.add_router("/health", health_router, tags=["health"])
api.add_router("/demo", demo_router, tags=["demo"])
api.add_router("", accounts_router, tags=["accounts"])
api.add_router("/organisations", organisations_router, tags=["organisations"])
api.add_router("/startups", startups_router, tags=["startups"])
api.add_router("", jobs_router, tags=["jobs"])
api.add_router("/notifications", notifications_router, tags=["notifications"])
api.add_router("/matches", matching_router, tags=["matching"])
