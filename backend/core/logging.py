"""One logging setup: structlog JSON, one line per request, no PII."""

import logging
import re
import sys
import time
import uuid

import structlog

# Keys that must never reach a log line (CLAUDE.md privacy rules).
_BLOCKED = {"name", "display_name", "email", "phone", "token", "authorization", "password", "bio", "cookie"}


def scrub_pii(_logger, _method, event_dict):
    for key in list(event_dict):
        if key.lower() in _BLOCKED or any(b in key.lower() for b in ("token", "password", "email")):
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            scrub_pii,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


# A client-supplied id is kept only if it is short and plain; anything else could forge log lines or bloat them.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestLogMiddleware:
    """Assigns a request_id and writes exactly one JSON line per request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.log = structlog.get_logger("request")

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        request.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.monotonic()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-ID"] = request_id
            return response
        finally:
            self.log.info(
                "request",
                method=request.method,
                path=request.path,
                status=status,
                ms=round((time.monotonic() - start) * 1000, 1),
                member_id=getattr(request, "member_id", None),
            )
