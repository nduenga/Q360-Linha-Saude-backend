from .base import *

DEBUG = False

# REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"] is JSONParser only (matches
# ART-006: every requestBody is `application/json`) — APIClient must match
# that in tests instead of defaulting to multipart. This key is read from
# inside the REST_FRAMEWORK dict, not as a top-level Django setting.
REST_FRAMEWORK = {**REST_FRAMEWORK, "TEST_REQUEST_DEFAULT_FORMAT": "json"}

# S01-PERSISTENCE-001 (see OPEN_DECISIONS.md): no SQLite fallback here
# either — tests/conftest.py's `django_db_modify_db_settings` fixture
# starts a disposable PostgreSQL container (Testcontainers) for the test
# session unless Q360_TEST_POSTGRES=true points at an already-running
# instance via the POSTGRES_* env vars above.
