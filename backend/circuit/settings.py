from urllib.parse import unquote, urlparse

from circuit.config import ROOT, load_config

cfg = load_config()

ENV = cfg.env
DEBUG = cfg.debug
SECRET_KEY = cfg.secret_key
ALLOWED_HOSTS = cfg.csv(cfg.allowed_hosts)
ROOT_URLCONF = "circuit.urls"
WSGI_APPLICATION = "circuit.wsgi.application"
ASGI_APPLICATION = "circuit.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
BASE_DIR = ROOT / "backend"

INSTALLED_APPS = [
    "core.admin_config.CircuitAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.gis",
    "django.contrib.postgres",
    "corsheaders",
    "ninja",
    "core",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "apps.organisations",
    "apps.accounts",
    "apps.matching",
    "apps.startups",
    "apps.jobs",
    "apps.intros",
    "apps.circuits",
    "apps.notifications",
    "apps.moderation",
    "apps.events",
    "apps.dashboard",
    "apps.social",
    "apps.messaging",
]

MIDDLEWARE = [
    "core.logging.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Security headers sit outside everything that can answer early (CORS preflight, redirects, errors).
    "core.security.SecurityHeadersMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

_db = urlparse(cfg.database_url)
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": _db.path.lstrip("/"),
        "USER": unquote(_db.username or ""),
        "PASSWORD": unquote(_db.password or ""),
        "HOST": _db.hostname,
        "PORT": _db.port or 5432,
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Circuit-specific settings -------------------------------------------------
APP_URL = cfg.app_url
LANDING_URL = cfg.landing_url
API_URL = cfg.api_url
REDIS_URL = cfg.redis_url
ADMIN_PATH = cfg.admin_path
DEMO_AUTH = cfg.demo_auth
DEMO_PUBLIC = cfg.demo_public
SUPABASE_URL = cfg.supabase_url
SUPABASE_JWT_AUDIENCE = cfg.supabase_jwt_audience
SUPABASE_JWT_ALG = cfg.supabase_jwt_alg
SUPABASE_SERVICE_ROLE_KEY = cfg.supabase_service_role_key
STORAGE_PROVIDER = cfg.storage_provider
MEDIA_ROOT = BASE_DIR / ".media"  # STORAGE_PROVIDER=local only (dev)
STORAGE_BUCKETS = {"post": "posts", "message": "messages"}  # private buckets; reads use short-lived signed URLs
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MEDIA_VARIANT_WIDTHS = (1440, 480)
MEDIA_MAX_PIXELS = 40_000_000  # decompression-bomb guard
LLM_PROVIDER = cfg.llm_provider
GEMINI_API_KEY = cfg.gemini_api_key
GROQ_API_KEY = cfg.groq_api_key
ANTHROPIC_API_KEY = cfg.anthropic_api_key
EMBEDDING_PROVIDER = cfg.embedding_provider
EMAIL_FROM = cfg.email_from
SUPPORT_EMAIL = cfg.support_email
SEED_CITY = {"name": cfg.seed_city_name, "lat": cfg.seed_city_lat, "lng": cfg.seed_city_lng}
CSRF_TRUSTED_ORIGINS = cfg.csv(cfg.csrf_trusted_origins)

# CORS: exact origins (+ the staging preview regex). Bearer tokens, so no cookies cross origins.
CORS_ALLOWED_ORIGINS = cfg.csv(cfg.cors_allowed_origins)
CORS_ALLOWED_ORIGIN_REGEXES = [cfg.cors_preview_regex] if cfg.cors_preview_regex else []
CORS_URLS_REGEX = r"^/api/"
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["authorization", "content-type", "x-request-id"]
CORS_EXPOSE_HEADERS = ["x-request-id"]
CORS_PREFLIGHT_MAX_AGE = 600

# Security headers and request limits (PRODUCTION.md §3)
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 8 * 3600
if ENV != "dev":  # demo is on the public internet too
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/health"]  # Cloud Run health checks arrive over plain HTTP
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Cloud Run terminates TLS
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Rate limits: (max requests, window in seconds) per member per action (core/ratelimit.py)
RATE_LIMITS = {
    "extraction": (10, 3600),
    "intro": (10, 86400),
    "application": (30, 86400),
    "report": (10, 86400),
    "claim": (5, 86400),
    "org_join": (10, 3600),
    "verify": (5, 86400),
    "post": (10, 86400),
    "reply": (60, 86400),
    "reaction": (300, 3600),
    "upload": (40, 86400),
    "message": (300, 86400),
    "conversation_start": (10, 86400),
    "connection_request": (20, 86400),
}

# Social (F15-F17)
PULSE_WINDOW_DAYS = 7
PULSE_PAGE_SIZE = 20
TODAY_WINDOW_HOURS = 24
DROP_SIZE = 3
DROP_REPEAT_DAYS = 14  # nobody is dropped to the same member twice within this many days
DROP_TZ = "Asia/Kolkata"  # drops are built for the IST calendar day, ready at 08:00

EMAIL_BACKEND = {
    "console": "django.core.mail.backends.console.EmailBackend",
    "disabled": "django.core.mail.backends.dummy.EmailBackend",
    "resend": "django.core.mail.backends.smtp.EmailBackend",
}[cfg.email_backend]

# Matching weights (CLAUDE.md: weights live in settings)
MATCH_WEIGHTS = {"complementarity": 0.5, "affinity": 0.2, "trust_path": 0.15, "timing": 0.1, "load_penalty": 0.05}
MATCH_BRIDGE_SHARE = 0.25
MATCH_TOP_N = 20  # matches kept per member
MATCH_MIN_SIMILARITY = 0.8  # text-embedding cosine needed for a "similar capability" to count; tune with eval_matching
MATCH_MIN_COMPLEMENTARITY = 0.05  # below this the pair is not a need/offer fit at all and is not shown
MATCH_KNN = 30  # nearest-neighbour candidates fetched per need/offer
MATCH_MAX_PER_SECTOR = 5  # diversity: at most this many matches from one sector in a member's list
MATCH_MAX_APPEARANCES = 30  # capacity: one person is shown in at most this many members' lists
MATCH_CACHE_TTL = 6 * 3600

INTRO_WEEKLY_LIMIT = 3  # warm intros one member may send per rolling 7 days (a target's own cap is open_intro_slots)
INTRO_EXPIRY_DAYS = 7

CIRCUIT_CONSENT_HOURS = 72
DASHBOARD_MIN_COUNT = 5  # partner dashboards never show a count below this (CLAUDE.md privacy rules)
DASHBOARD_CACHE_SECONDS = 300
HEATMAP_CELL_DEGREES = 0.02  # about 2 km
CIRCUIT_MIN_LEG_SCORE = 0.2  # a loop is only proposed if even its weakest handover is at least this good a match
STUDENT_MAX_DISTANCE_KM = 25

from core.logging import configure_logging  # noqa: E402

configure_logging(cfg.log_level)
