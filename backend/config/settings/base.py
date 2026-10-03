"""Shared, secure-by-default Django settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Fast local dev (no Docker): loads backend/.env into the process so
# `manage.py runserver` picks up POSTGRES_*/OIDC_*/CORS_* without having to
# export them by hand every session - see DEV_SETUP.md. `override=False`
# (the default) means real environment variables set by docker-compose or
# a production host always win; this is a convenience layered underneath
# them, never a replacement.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
        raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
    SECRET_KEY = "s01-development-only-key-change-me"

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host]
# Render assigns the public hostname at deploy time.  Trust only that exact
# hostname automatically; custom domains remain an explicit DJANGO_ALLOWED_HOSTS
# deployment setting.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "apps.foundation",
    "apps.product",
    "apps.client",
    "apps.eligibility",
    "apps.pricing",
    "apps.quote",
    "apps.policy",
    "apps.claims",
    "apps.customer_portal",
    "apps.staff_accounts",
    "apps.platform_admin",
    "apps.business_config",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Must run before CommonMiddleware (django-cors-headers requirement).
    # Not an ART-006 concern: the contract is silent on browser origins, this
    # is pure local/deployment wiring so the separately-built React frontend
    # (a different origin in dev: Vite on :5173 vs Django on :8000) can call
    # the API at all. CORS_ALLOWED_ORIGINS is empty by default (nothing
    # allowed) unless an environment explicitly sets it - see development.py
    # and production.py.
    "corsheaders.middleware.CorsMiddleware",
    "apps.foundation.interfaces.middleware.CorrelationIdMiddleware",
    "apps.foundation.interfaces.middleware.RequestTelemetryMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.foundation.interfaces.middleware.IdempotencyMiddleware",
    "apps.foundation.interfaces.middleware.RateLimitMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.foundation.interfaces.middleware.ActorContextCleanupMiddleware",
]

# Mutating API commands are protected by an Idempotency-Key in deployed
# environments.  The isolated unit-test setting turns this off and the S9
# integration tests explicitly turn it on, which keeps old domain tests
# focused on their concern while exercising the real interceptor separately.
IDEMPOTENCY_REQUIRED = os.environ.get("Q360_IDEMPOTENCY_REQUIRED", "true").lower() == "true"

# A small, defensive application-level limit is deliberately configurable.
# Deployments with a gateway/WAF can set the value to 0 and make that layer
# authoritative; this guard still provides a safe default for direct access.
RATE_LIMIT_REQUESTS = int(os.environ.get("Q360_RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("Q360_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_EXEMPT_PATHS = {"/health/live", "/health/ready"}

CORS_ALLOWED_ORIGINS = [
    origin for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin
]
# The frontend sends Authorization/Idempotency-Key/X-Correlation-Id, none of
# which are in the CORS-safelisted header set, so they must be listed
# explicitly or the browser preflight (OPTIONS) rejects the real request.
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "idempotency-key",
    "x-correlation-id",
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
    "quote": "apps.quote.infrastructure.migrations",
    "policy": "apps.policy.infrastructure.migrations",
    "claims": "apps.claims.infrastructure.migrations",
    "business_config": "apps.business_config.infrastructure.migrations",
    "customer_portal": "apps.customer_portal.infrastructure.migrations",
    "staff_accounts": "apps.staff_accounts.infrastructure.migrations",
    "platform_admin": "apps.platform_admin.infrastructure.migrations",
}

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    # Render exposes its private Postgres connection through DATABASE_URL.
    # Keep the explicit POSTGRES_* configuration below as the local/Docker
    # fallback, so existing developer workflows remain unchanged.
    import dj_database_url

    _database_config = dj_database_url.parse(
        _database_url,
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
    _database_config.setdefault("OPTIONS", {})["options"] = f"-c search_path={DB_SCHEMA_SEARCH_PATH}"
    DATABASES = {"default": _database_config}
else:
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

# OPEN DECISION (Q360-S6-01, DECISIONS_TAKEN.md#S06-QUOTE-001): no approved
# document fixes the default quote validity period. Configurable per
# environment rather than hardcoded in apps/quote/application/quote_service.py.
QUOTE_DEFAULT_VALIDITY_DAYS = int(os.environ.get("QUOTE_DEFAULT_VALIDITY_DAYS", "30"))

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
    "DEFAULT_SCHEMA_CLASS": "config.openapi.schema.Q360AutoSchema",
}

# OpenTelemetry is optional at import time so a local developer can still run
# the project before installing the observability extra.  In production the
# dependency is installed and this flag enables API/service spans and OTLP
# export; no request body, Authorization header or business payload is ever
# recorded as a span attribute.
Q360_OTEL_ENABLED = os.environ.get("Q360_OTEL_ENABLED", "false").lower() == "true"
Q360_OTEL_SERVICE_NAME = os.environ.get("Q360_OTEL_SERVICE_NAME", "q360-core")
Q360_OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

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
    "VERSION": "1.4.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": False,
    "ENUM_NAME_OVERRIDES": {
        "QuoteStatusEnum": "apps.quote.domain.enums.QuoteStatus",
        "QuoteMemberStatusEnum": "apps.quote.domain.enums.QuoteMemberStatus",
        "ReviewTaskStatusEnum": "apps.quote.domain.enums.ReviewTaskStatus",
        "DocumentStatusEnum": "apps.quote.domain.enums.DocumentStatus",
        "PolicyStatusEnum": "apps.policy.domain.enums.PolicyStatus",
        "PolicyMemberStatusEnum": "apps.policy.domain.enums.PolicyMemberStatus",
        "ProductStatusEnum": "apps.product.domain.enums.ProductStatus",
        "PlanStatusEnum": "apps.product.domain.enums.PlanStatus",
        "VersionedConfigStatusEnum": "apps.product.domain.enums.VersionedConfigStatus",
        "TenantStatusEnum": ["ACTIVE", "SUSPENDED", "INACTIVE"],
        "PlatformAdminStatusEnum": ["ACTIVE", "DISABLED"],
    },
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SECURITY": [{"oauth2": ["q360.read"]}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "oauth2": {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "/api/v1/auth/login",
                        "scopes": {
                            "q360.read": "Leitura",
                            "q360.write": "Escrita",
                            "q360.approve": "Aprovação",
                            "q360.admin": "Administração/configuração",
                            "q360.audit": "Auditoria",
                        },
                    }
                },
            }
        }
    },
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

# --- Self-hosted staff identity (apps.staff_accounts) -------------------
# Replaces an external OIDC IdP (Auth0/Keycloak/...) with a token this
# backend issues itself (apps/staff_accounts/infrastructure/staff_token.py)
# — a legitimate PRODUCTION signing key, unlike OIDC_STATIC_VERIFICATION_KEY
# above. JwtActorAdapter (apps/foundation/infrastructure/jwt_actor_adapter.py)
# needs no change: it already resolves the verification key generically: an
# external JWKS if OIDC_JWKS_URL is set, else this key if set, else the dev
# escape hatch. Dev gets a fallback (same pattern as DJANGO_SECRET_KEY);
# config/settings/production.py requires this OR a real external IdP to be
# configured — never neither.
Q360_JWT_SIGNING_KEY = os.environ.get("Q360_JWT_SIGNING_KEY", "")

Q360_STAFF_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("Q360_STAFF_ACCESS_TOKEN_TTL_SECONDS", "1800"))

# --- Platform administrator identity ----------------------------------
# MUST differ from Q360_JWT_SIGNING_KEY.
PLATFORM_ADMIN_JWT_SIGNING_KEY = os.environ.get("PLATFORM_ADMIN_JWT_SIGNING_KEY", "")
PLATFORM_ADMIN_JWT_ISSUER = os.environ.get("PLATFORM_ADMIN_JWT_ISSUER", "q360-platform")
PLATFORM_ADMIN_JWT_AUDIENCE = os.environ.get("PLATFORM_ADMIN_JWT_AUDIENCE", "q360-platform-api")
PLATFORM_ADMIN_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("PLATFORM_ADMIN_ACCESS_TOKEN_TTL_SECONDS", "1800"))
Q360_STAFF_REFRESH_TOKEN_TTL_SECONDS = int(os.environ.get("Q360_STAFF_REFRESH_TOKEN_TTL_SECONDS", str(30 * 24 * 3600)))
# Same lockout policy shape as OD-PORTAL-003 (customer portal), applied to
# staff logins instead of OTP verification.
Q360_STAFF_MAX_FAILED_ATTEMPTS = int(os.environ.get("Q360_STAFF_MAX_FAILED_ATTEMPTS", "5"))
Q360_STAFF_LOCKOUT_MINUTES = int(os.environ.get("Q360_STAFF_LOCKOUT_MINUTES", "30"))
Q360_STAFF_LOGIN_RATE_LIMIT = int(os.environ.get("Q360_STAFF_LOGIN_RATE_LIMIT", "10"))
Q360_STAFF_LOGIN_RATE_WINDOW_SECONDS = int(os.environ.get("Q360_STAFF_LOGIN_RATE_WINDOW_SECONDS", "60"))

# --- Customer Portal (ROADMAP_PORTAL_CLIENTE.md Fase 0) ----------------
# Deliberately isolated from OIDC_*/SECRET_KEY above: a customer-portal
# token must never be verifiable/forgeable with the staff IdP's key or
# Django's own SECRET_KEY ("nunca reaproveita os scopes/roles internos").
CUSTOMER_PORTAL_JWT_SECRET = os.environ.get("CUSTOMER_PORTAL_JWT_SECRET", "")
CUSTOMER_PORTAL_TOKEN_TTL_SECONDS = int(os.environ.get("CUSTOMER_PORTAL_TOKEN_TTL_SECONDS", "1800"))
# OD-PORTAL-001 (Product Owner decision 2026-09-22): email OTP only.
CUSTOMER_PORTAL_OTP_TTL_SECONDS = int(os.environ.get("CUSTOMER_PORTAL_OTP_TTL_SECONDS", "600"))
CUSTOMER_PORTAL_EMAIL_FROM = os.environ.get("CUSTOMER_PORTAL_EMAIL_FROM", "no-reply@q360.example")
# OD-PORTAL-003 (Product Owner decision 2026-09-22): 5 tentativas / 30 min.
CUSTOMER_PORTAL_MAX_FAILED_ATTEMPTS = int(os.environ.get("CUSTOMER_PORTAL_MAX_FAILED_ATTEMPTS", "5"))
CUSTOMER_PORTAL_LOCKOUT_MINUTES = int(os.environ.get("CUSTOMER_PORTAL_LOCKOUT_MINUTES", "30"))
# Stricter than RATE_LIMIT_REQUESTS above: these 2 endpoints are the only
# ones a caller can hit before proving anything, so they are the natural
# brute-force target for guessing quoteNumber/registrationNumber pairs
# (see apps/customer_portal/interfaces/rate_limit.py).
CUSTOMER_PORTAL_LOGIN_RATE_LIMIT = int(os.environ.get("CUSTOMER_PORTAL_LOGIN_RATE_LIMIT", "10"))
CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS = int(
    os.environ.get("CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS", "60")
)
# Compensating control for request-access now revealing exactly which of
# quoteNumber/registrationNumber is wrong (Product Owner decision,
# 2026-09-26 — see apps.customer_portal.domain.errors module docstring).
# Deliberately much tighter than the pair above, and keyed by IP alone
# (apps.customer_portal.interfaces.rate_limit.is_ip_rate_limited) - email
# is attacker-controlled and unverified at this point, so a per-email
# bucket alone is trivially bypassed by varying it on every request.
CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = int(os.environ.get("CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP", "5"))
CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS_PER_IP = int(
    os.environ.get("CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS_PER_IP", "900")
)

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


EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.environ.get(
    "EMAIL_HOST",
    "",
)

EMAIL_PORT = int(
    os.environ.get(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_HOST_USER = os.environ.get(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = os.environ.get(
    "EMAIL_HOST_PASSWORD",
    "",
)

EMAIL_USE_TLS = (
    os.environ.get(
        "EMAIL_USE_TLS",
        "true",
    ).lower()
    == "true"
)

EMAIL_USE_SSL = (
    os.environ.get(
        "EMAIL_USE_SSL",
        "false",
    ).lower()
    == "true"
)

EMAIL_TIMEOUT = int(
    os.environ.get(
        "EMAIL_TIMEOUT",
        "20",
    )
)