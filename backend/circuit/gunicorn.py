"""gunicorn settings for Cloud Run (docker/backend/Dockerfile runs `gunicorn -c circuit/gunicorn.py circuit.wsgi`).

Cloud Run sends up to `concurrency` requests at once to one container (deploy/gcp/app.toml sets 8). Two worker processes with
four threads each is also 8, so the container never holds more work than it was promised. Threads share memory, so the fastembed
model and the Django app are loaded twice, not eight times.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"  # Cloud Run tells the container which port with $PORT
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

timeout = 60  # same as the Cloud Run request timeout; a hung worker is replaced
graceful_timeout = 8  # Cloud Run sends SIGTERM and kills the container 10 s later
keepalive = 75  # longer than Google's front end keeps idle connections open

# A worker that restarts every ~1000 requests gives memory back (Pillow, numpy) without anyone noticing.
max_requests = 1000
max_requests_jitter = 100

worker_tmp_dir = "/dev/shm"  # heartbeat files in memory: the container's disk may be read-only or slow
accesslog = None  # RequestLogMiddleware writes exactly one JSON line per request

# gunicorn's own messages (starting, a worker restarting, a crash) go to stdout as JSON with a severity. By default they go to
# stderr as plain text, which Cloud Run would show as ERROR even for "Booting worker".
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.logging.StdlibJsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "json"}},
    "loggers": {
        "gunicorn.error": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "gunicorn.access": {"level": "INFO", "handlers": [], "propagate": False},
    },
}

control_socket_disable = True  # gunicorn 26's admin socket is not used here, and the app user has no home folder for it
