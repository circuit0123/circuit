from ninja import NinjaAPI

from core.errors import install_handlers
from core.health import router as health_router

api = NinjaAPI(
    title="Circuit API",
    version="1.0.0",
    description="Circuit backend. Errors always use {error: {code, message, details}}; lists use {items, count, next_offset}.",
    openapi_url="/openapi.json",
    docs_url="/docs",
)
install_handlers(api)
api.add_router("/health", health_router, tags=["health"])
