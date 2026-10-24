"""One error format for every endpoint: {"error": {"code", "message", "details"}}."""

from django.core.exceptions import RequestDataTooBig
from django.http import Http404
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, HttpError, ValidationError
from ninja.errors import AuthorizationError as NinjaAuthorizationError
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list | dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Raise from services/routers; becomes the standard error response."""

    def __init__(self, status: int, code: str, message: str, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details


class NotFound(ApiError):
    def __init__(self, message: str = "Not found"):
        super().__init__(404, "not_found", message)


class Forbidden(ApiError):
    def __init__(self, message: str = "You do not have permission to do this"):
        super().__init__(403, "forbidden", message)


class AccountSuspended(ApiError):
    def __init__(self):
        super().__init__(403, "account_suspended", "This account is suspended")


class AccountDeleted(ApiError):
    def __init__(self):
        super().__init__(403, "account_deleted", "This account has been deleted")


class ConsentRequired(ApiError):
    def __init__(self):
        super().__init__(403, "consent_required", "Please accept the current Privacy Policy and Terms to continue.")


class BetaRequired(ApiError):
    def __init__(self):
        super().__init__(403, "beta_required", "Circuit is invite-only for now. Enter an invite code or join the waitlist.")


class Conflict(ApiError):
    def __init__(self, message: str, code: str = "conflict"):
        super().__init__(409, code, message)


class RateLimited(ApiError):
    def __init__(self, message: str = "Too many requests, try again later", retry_after: int | None = None):
        super().__init__(429, "rate_limited", message, {"retry_after": retry_after} if retry_after else None)
        self.retry_after = retry_after


class Unauthenticated(ApiError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(401, "unauthenticated", message)


class ServiceUnavailable(ApiError):
    def __init__(self, message: str, code: str = "service_unavailable"):
        super().__init__(503, code, message)


def _respond(api: NinjaAPI, request, status: int, code: str, message: str, details=None):
    return api.create_response(request, {"error": {"code": code, "message": message, "details": details}}, status=status)


def install_handlers(api: NinjaAPI) -> None:
    @api.exception_handler(ApiError)
    def _api_error(request, exc: ApiError):
        return _respond(api, request, exc.status, exc.code, exc.message, exc.details)

    @api.exception_handler(ValidationError)
    def _validation(request, exc: ValidationError):
        return _respond(api, request, 422, "validation_error", "Invalid request", exc.errors)

    @api.exception_handler(AuthenticationError)
    def _unauth(request, exc):
        return _respond(api, request, 401, "unauthenticated", "Authentication required")

    @api.exception_handler(NinjaAuthorizationError)
    def _forbidden(request, exc):
        return _respond(api, request, 403, "forbidden", "You do not have permission to do this")

    @api.exception_handler(RequestDataTooBig)
    def _too_big(request, exc):
        return _respond(api, request, 413, "payload_too_large", "Request body is too large")

    @api.exception_handler(Http404)
    def _404(request, exc):
        return _respond(api, request, 404, "not_found", "Not found")

    @api.exception_handler(HttpError)
    def _http(request, exc: HttpError):
        return _respond(api, request, exc.status_code, "error", str(exc.message))

    @api.exception_handler(Exception)
    def _unhandled(request, exc: Exception):
        import structlog

        structlog.get_logger("errors").error("unhandled", exc_type=type(exc).__name__, exc_info=True)
        return _respond(api, request, 500, "internal_error", "Something went wrong")


def api_not_found(request, *args, **kwargs):
    """Catch-all for /api/... paths no router matched, so even these use the standard error format."""
    from django.http import JsonResponse

    body = {"error": {"code": "not_found", "message": "Not found", "details": None}}
    return JsonResponse(body, status=404)


def _json_error(status: int, code: str, message: str):
    from django.http import JsonResponse

    return JsonResponse({"error": {"code": code, "message": message, "details": None}}, status=status)


# Django's own error pages (anything outside the API router: unknown non-API paths, errors in middleware, the admin).
# Django calls these only when DEBUG is off, which is every environment except dev. They never show a stack trace.
def handler404(request, exception=None):
    return _json_error(404, "not_found", "Not found")


def handler403(request, exception=None):
    return _json_error(403, "forbidden", "You do not have permission to do this")


def handler400(request, exception=None):
    return _json_error(400, "bad_request", "Bad request")


def handler500(request):
    return _json_error(500, "internal_error", "Something went wrong")


class ApiErrorFormatMiddleware:
    """Ninja answers a wrong HTTP method on a real route with a bare "Method not allowed". Make it our one error format.

    Innermost on purpose: the response is replaced before CORS and the security headers are added to it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.path_info.startswith("/api/")
            and response.status_code == 405
            and "json" not in response.get("Content-Type", "")
        ):
            replacement = _json_error(405, "method_not_allowed", "That method is not allowed on this route")
            if response.has_header("Allow"):
                replacement["Allow"] = response["Allow"]
            return replacement
        return response
