
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "local-development-key-change-before-production",
)

DEBUG = os.environ.get(
    "DJANGO_DEBUG", "1"
).strip().lower() in {"1", "true", "yes"}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1",
    ).split(",")
    if host.strip()
]

RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "core.apps.CoreConfig",
    "academics.apps.AcademicsConfig",
    "finance.apps.FinanceConfig",
    "procurement.apps.ProcurementConfig",
    "operations.apps.OperationsConfig",

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Use the database URL when the hosting environment provides one.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
        )
    }
else:
    # Read local database credentials from .env.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "greenhill_eid")),
            "USER": os.environ.get("DB_USER",os.environ.get("POSTGRES_USER", "postgres"),),
            "PASSWORD": os.environ.get("DB_PASSWORD",os.environ.get("POSTGRES_PASSWORD", ""),),
            "HOST": os.environ.get("DB_HOST",os.environ.get("POSTGRES_HOST", "localhost"), ),
            "PORT": os.environ.get( "DB_PORT",os.environ.get("POSTGRES_PORT", "5432"),),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured(
        "Only PostgreSQL is supported. Check your database configuration."
    )


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "GreenHill Executive Intelligence Dashboard API",
    "DESCRIPTION": (
        "API documentation for the GreenHill Executive Intelligence Dashboard."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Docs groups in the same order as the frontend sidebar. Every view sets one of these
    # with @extend_schema(tags=[...]); core/tests/test_api_docs.py enforces it.
    "TAGS": [
        {"name": "Academics - Students", "description": "Students, sections and attendance."},
        {
            "name": "Academics - Performance",
            "description": "Academic records, grade results and homework.",
        },
        {"name": "Academics - Co-Curricular", "description": "Clubs, societies and events."},
        {"name": "Academics - Staff", "description": "Academic staff records."},
        {"name": "Finance - Budgets", "description": "Fiscal years, departments and budgets."},
        {"name": "Finance - Liabilities", "description": "Creditors and outstanding liabilities."},
        {"name": "Finance - Revenue", "description": "Revenue records and monthly targets."},
        {"name": "Procurement", "description": "Vendors and procurement transactions."},
        {
            "name": "Operations - HR & Workforce",
            "description": "Workforce units, employees, staff attendance and the HR dashboard.",
        },
        {
            "name": "Operations - Facilities & Maintenance",
            "description": "Campus facilities and their operating status.",
        },
        {
            "name": "Operations - Assets & Equipment",
            "description": "Asset register, condition and the asset dashboard.",
        },
        {"name": "System", "description": "Service health."},
    ],
    # One name for choice sets shared by several fields, so the schema has no duplicates.
    "ENUM_NAME_OVERRIDES": {
        "ProcurementCategoryEnum": "procurement.models.ProcurementCategory",
    },
}

# CORS configuration
CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "https://greenhill-eid-frontend.onrender.com,"
        "https://greenhill-auth-frontend2.onrender.com",
    ).split(",")
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "",
    ).split(",")
    if origin.strip()
]

FRONTEND_URL = os.environ.get(
    "FRONTEND_URL",
    "http://localhost:5173",
).rstrip("/")

if FRONTEND_URL.startswith("https://"):
    if FRONTEND_URL not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(FRONTEND_URL)


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
