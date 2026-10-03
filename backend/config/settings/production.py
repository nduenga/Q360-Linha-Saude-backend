from .base import *

DEBUG = False
# Render terminates TLS at its proxy and forwards the original scheme to the
# application.  Without this Django would see every request as HTTP and
# SECURE_SSL_REDIRECT would loop indefinitely.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

if OIDC_STATIC_VERIFICATION_KEY:
    raise RuntimeError(
        "OIDC_STATIC_VERIFICATION_KEY is a local/dev-only escape hatch and "
        "must not be set in production; configure OIDC_JWKS_URL or "
        "Q360_JWT_SIGNING_KEY instead."
    )
# Exactly one identity provider must be configured: either a real external
# OIDC IdP (Auth0/Keycloak/...), or this backend's own self-hosted signing
# key (apps.staff_accounts) - Q360-S1-03 resource-server configuration.
_has_external_idp = bool(OIDC_ISSUER and OIDC_AUDIENCE and OIDC_JWKS_URL)
_has_self_hosted_idp = bool(Q360_JWT_SIGNING_KEY)
if not (_has_external_idp or _has_self_hosted_idp):
    raise RuntimeError(
        "No identity provider configured: set OIDC_ISSUER+OIDC_AUDIENCE+OIDC_JWKS_URL "
        "for an external IdP, or Q360_JWT_SIGNING_KEY for the self-hosted one."
    )
if len(Q360_JWT_SIGNING_KEY) < 32 and _has_self_hosted_idp:
    raise RuntimeError("Q360_JWT_SIGNING_KEY must be at least 32 characters in production.")

if not CUSTOMER_PORTAL_JWT_SECRET:
    raise RuntimeError(
        "CUSTOMER_PORTAL_JWT_SECRET must be set in production (ROADMAP_PORTAL_CLIENTE.md "
        "Fase 0 — must never fall back to SECRET_KEY or an OIDC key)."
    )


if not PLATFORM_ADMIN_JWT_SIGNING_KEY:
    raise RuntimeError("PLATFORM_ADMIN_JWT_SIGNING_KEY must be configured in production.")
if len(PLATFORM_ADMIN_JWT_SIGNING_KEY) < 32:
    raise RuntimeError("PLATFORM_ADMIN_JWT_SIGNING_KEY must be at least 32 characters in production.")
