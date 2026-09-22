from .base import *

DEBUG = False

# Existing focused domain tests predate S9's HTTP idempotency contract.  The
# S9 integration suite enables this setting explicitly to validate the real
# middleware behaviour without forcing every unit fixture to manufacture an
# HTTP retry key.
IDEMPOTENCY_REQUIRED = False
RATE_LIMIT_REQUESTS = 0

# REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"] is JSONParser only (matches
# ART-006: every requestBody is `application/json`) — APIClient must match
# that in tests instead of defaulting to multipart. This key is read from
# inside the REST_FRAMEWORK dict, not as a top-level Django setting.
REST_FRAMEWORK = {**REST_FRAMEWORK, "TEST_REQUEST_DEFAULT_FORMAT": "json"}

CUSTOMER_PORTAL_JWT_SECRET = CUSTOMER_PORTAL_JWT_SECRET or "test-only-portal-secret-32-bytes-min"
# Captures sent emails in django.core.mail.outbox instead of actually
# sending them — lets tests assert an OTP email was sent without a real
# SMTP server.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CUSTOMER_PORTAL_LOGIN_RATE_LIMIT = 0  # Same rationale as RATE_LIMIT_REQUESTS = 0 above.

# S01-PERSISTENCE-001 (see OPEN_DECISIONS.md): no SQLite fallback here
# either — tests/conftest.py's `django_db_modify_db_settings` fixture
# starts a disposable PostgreSQL container (Testcontainers) for the test
# session unless Q360_TEST_POSTGRES=true points at an already-running
# instance via the POSTGRES_* env vars above.
