"""Shared, secure-by-default Django settings."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
        raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
    SECRET_KEY = "s01-development-only-key-change-me"

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "apps.foundation",
    "apps.product",
    "apps.client",
    "apps.eligibility",
    "apps.pricing",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.foundation.interfaces.middleware.CorrelationIdMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.foundation.interfaces.middleware.ActorContextCleanupMiddleware",
]

# The `q360` schema (ART-005/ART-012) owns all business tables. `public` is
# listed first so Django's own internal apps (contenttypes, auth) keep
# landing in `public`; our migrations always qualify DDL with `q360.`
# explicitly, so lookups for our (unqualified) db_table names still resolve
# via this search_path. See apps/foundation/infrastructure/models.py.
DB_SCHEMA_SEARCH_PATH = "public,q360"

# Foundation's migrations live under infrastructure/ to keep Clean
# Architecture layering (DOC-004 s3) instead of Django's default
# `<app>/migrations/` location.
MIGRATION_MODULES = {
    "foundation": "apps.foundation.infrastructure.migrations",
    "product": "apps.product.infrastructure.migrations",
    "client": "apps.client.infrastructure.migrations",
    "eligibility": "apps.eligibility.infrastructure.migrations",
    "pricing": "apps.pricing.infrastructure.migrations",
}

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "q360"),
        "USER": os.environ.get("POSTGRES_USER", "q360"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "q360"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {"options": f"-c search_path={DB_SCHEMA_SEARCH_PATH}"},
    }
}

# Raw bytes of an uploaded member-import file (Q360-S3-04): ART-005 has no
# blob/file-content column on `import_job` (only metadata: filename,
# checksum, row counts), so the file itself lives on this storage, at a
# path deterministically derived from the ImportJob id — see
# apps/client/application/import_service.py. Not exposed over HTTP
# (no MEDIA_URL): read back only by the commit step, server-side.
MEDIA_ROOT = BASE_DIR / "media"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# ART-006 paths never have a trailing slash (DOC-004 s2: ART-006 is the
# final HTTP authority) — APPEND_SLASH would only ever cause an unwanted
# redirect here, never a correct match.
APPEND_SLASH = False

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # DOC-001 s20: "Todas as operações devem ser autenticadas e
    # autorizadas." / Q360-S1-03 acceptance criteria: "Endpoints protegidos
    # por default". A view must opt OUT explicitly (AllowAny) to be public;
    # none exist yet in the approved V1 scope.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.foundation.interfaces.authentication.JwtActorAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "apps.foundation.interfaces.exception_handler.q360_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular introspects the Django code to render a browsable API
# doc — useful to see what is ACTUALLY implemented so far during
# development, but it is NOT the contract: ART-006
# (docs/artifacts/ART-006-openapi/Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml)
# is. The frontend's own API client is generated from that static ART-006
# file directly (ART-010 "Architecture" sheet: "API client | Generated
# from ART-006 OpenAPI where practical"), not from this endpoint — never
# hand a drf-spectacular URL to the frontend team as "the" spec.
SPECTACULAR_SETTINGS = {
    "TITLE": "Q360 Health Underwriting & Pricing Core (as-implemented, dev-only)",
    "DESCRIPTION": (
        "Auto-generated from the current Django code — for internal debugging only. "
        "The approved contract is ART-006 (Q360-MVP-ART-006), not this document."
    ),
    "VERSION": "0.0.0-dev",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- OAuth2/OIDC Resource Server (Q360-S1-03) --------------------------
# OPEN DECISION (OD-009 / backend/OPEN_DECISIONS.md#S01-AUTH-001): the
# concrete Identity Provider and exact claim names are not fixed by any
# approved Q360 document. Configure per environment; do not hardcode a
# vendor's claim shape in code.
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "")
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")
OIDC_JWKS_URL = os.environ.get("OIDC_JWKS_URL", "")
OIDC_TENANT_CLAIM = os.environ.get("OIDC_TENANT_CLAIM", "tenant_id")
OIDC_ROLES_CLAIM = os.environ.get("OIDC_ROLES_CLAIM", "roles")
# "scope" (space-delimited string) is the standard OAuth2 claim name
# (RFC 8693) carrying ART-006's fixed q360.read/write/approve/admin/audit
# values — less open than tenant/roles, but still per-environment/IdP.
OIDC_SCOPE_CLAIM = os.environ.get("OIDC_SCOPE_CLAIM", "scope")
OIDC_ALGORITHMS = [
    alg for alg in os.environ.get("OIDC_ALGORITHMS", "RS256").split(",") if alg
]
# Dev/test-only escape hatch when no OIDC provider is running locally;
# config/settings/production.py refuses to start if this is set.
OIDC_STATIC_VERIFICATION_KEY = os.environ.get("OIDC_STATIC_VERIFICATION_KEY", "")

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "apps.foundation.interfaces.middleware.CorrelationIdLogFilter",
        },
    },
    "formatters": {
        "structured": {
            "format": (
                "%(asctime)s level=%(levelname)s logger=%(name)s "
                "correlation_id=%(correlation_id)s message=%(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["correlation_id"],
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
