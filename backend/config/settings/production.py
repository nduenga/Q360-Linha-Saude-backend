from .base import *

DEBUG = False
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

if OIDC_STATIC_VERIFICATION_KEY:
    raise RuntimeError(
        "OIDC_STATIC_VERIFICATION_KEY is a local/dev-only escape hatch and "
        "must not be set in production; configure OIDC_JWKS_URL instead."
    )
if not (OIDC_ISSUER and OIDC_AUDIENCE and OIDC_JWKS_URL):
    raise RuntimeError(
        "OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL must all be set in production "
        "(Q360-S1-03 resource-server configuration)."
    )
