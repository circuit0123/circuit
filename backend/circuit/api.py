from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.accounts.onboarding_api import router as onboarding_router
from apps.accounts.privacy_api import router as privacy_router
from apps.accounts.settings_api import router as settings_router
from apps.beta.api import router as beta_router
from apps.circuits.api import router as circuits_router
from apps.dashboard.api import router as dashboard_router
from apps.intros.api import router as intros_router
from apps.jobs.api import router as jobs_router
from apps.matching.api import router as matching_router
from apps.messaging.api import router as messaging_router
from apps.moderation.api import router as moderation_router
from apps.moderation.blocks_api import router as blocks_router
from apps.notifications.api import router as notifications_router
from apps.notifications.unsubscribe_api import router as unsubscribe_router
from apps.organisations.api import router as organisations_router
from apps.social.api import router as social_router
from apps.startups.api import router as startups_router
from apps.startups.search_api import router as search_router
from core.auth import SupabaseAuth
from core.cities import router as cities_router
from core.config_api import router as config_router
from core.demo import router as demo_router
from core.errors import install_handlers
from core.health import router as health_router

api = NinjaAPI(
    title="Circuit API",
    version="1.2.0",
    description="Circuit backend. Errors always use {error: {code, message, details}}; lists use {items, count, next_offset}.",
    openapi_url=None if settings.ENV == "production" else "/openapi.json",  # no public API map in production
    docs_url=None if settings.ENV == "production" else "/docs",
    auth=SupabaseAuth(),  # default for every endpoint; public ones opt out with auth=None
)
install_handlers(api)
api.add_router("/config", config_router, tags=["config"])
api.add_router("/cities", cities_router, tags=["config"])
api.add_router("", beta_router, tags=["beta"])
api.add_router("/health", health_router, tags=["health"])
api.add_router("/demo", demo_router, tags=["demo"])
api.add_router("", accounts_router, tags=["accounts"])
api.add_router("", settings_router, tags=["settings"])
api.add_router("", onboarding_router, tags=["accounts"])
api.add_router("", privacy_router, tags=["privacy"])
api.add_router("/organisations", organisations_router, tags=["organisations"])
api.add_router("/startups", startups_router, tags=["startups"])
api.add_router("/search", search_router, tags=["startups"])
api.add_router("", jobs_router, tags=["jobs"])
api.add_router("/notifications", notifications_router, tags=["notifications"])
api.add_router("", unsubscribe_router, tags=["notifications"])
api.add_router("/matches", matching_router, tags=["matching"])
api.add_router("/intros", intros_router, tags=["intros"])
api.add_router("/circuits", circuits_router, tags=["circuits"])
api.add_router("/dashboard", dashboard_router, tags=["dashboard"])
api.add_router("", social_router, tags=["social"])
api.add_router("/conversations", messaging_router, tags=["messaging"])
api.add_router("/reports", moderation_router, tags=["moderation"])
api.add_router("", blocks_router, tags=["moderation"])
if settings.ENV == "dev" and settings.STORAGE_PROVIDER == "local":
    from core.media_dev import router as media_dev_router

    api.add_router("/media/dev", media_dev_router, tags=["dev"])
