"""One logging setup: structlog JSON, one line per request, no PII."""

import json
import logging
import re
import sys
import time
import uuid

import structlog
from django.conf import settings

# Keys that must never reach a log line (CLAUDE.md privacy rules).
_BLOCKED = {"name", "display_name", "email", "phone", "token", "authorization", "password", "bio", "cookie"}


def scrub_pii(_logger, _method, event_dict):
    for key in list(event_dict):
        if key.lower() in _BLOCKED or any(b in key.lower() for b in ("token", "password", "email")):
            event_dict[key] = "[redacted]"
    return event_dict


# Cloud Logging reads `severity` and `message` from a JSON line and shows the rest as fields. Our own fields (level, event) stay,
# so nothing that reads them changes.
_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "warn": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "exception": "ERROR",
}


def cloud_logging(_logger, _method, event_dict):
    event_dict["severity"] = _SEVERITY.get(str(event_dict.get("level", "info")), "DEFAULT")
    event_dict.setdefault("message", event_dict.get("event"))
    return event_dict


class StdlibJsonFormatter(logging.Formatter):
    """Django's and gunicorn's own log lines (errors with a traceback, 'Not Found: /x') as one JSON line with a severity.
    Without this Cloud Run shows gunicorn's routine startup lines as errors, because they are written to stderr."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)  # Error Reporting groups errors by this stack trace
        return json.dumps(
            {"severity": _SEVERITY.get(record.levelname.lower(), "DEFAULT"), "message": message, "logger": record.name},
            ensure_ascii=False,
        )


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StdlibJsonFormatter())
    logging.basicConfig(handlers=[handler], level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            cloud_logging,
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
_TRACE_HEADER = re.compile(r"([0-9a-f]{32})/")  # X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=1


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
        trace = _TRACE_HEADER.match(request.headers.get("X-Cloud-Trace-Context", ""))
        if trace and settings.GOOGLE_CLOUD_PROJECT:  # lets Cloud Logging show all lines of one request together with its trace
            structlog.contextvars.bind_contextvars(
                **{"logging.googleapis.com/trace": f"projects/{settings.GOOGLE_CLOUD_PROJECT}/traces/{trace.group(1)}"}
            )
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
