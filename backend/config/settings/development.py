from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# S01-PERSISTENCE-001 (see OPEN_DECISIONS.md): PostgreSQL is mandatory, not
# optional, in every environment. The foundation migration
# (apps/foundation/infrastructure/migrations/0001_foundation_baseline.py)
# ports ART-012 DDL verbatim (schemas, jsonb, CHECK constraints) and cannot
# run on SQLite — a SQLite fallback would let `migrate` "succeed" against a
# schema that silently diverges from ART-005/ART-012, which is exactly what
# DOC-000 s3 P-08 forbids.
#
# Fast local dev does NOT require Docker: a native PostgreSQL install on
# the host (POSTGRES_HOST=localhost, POSTGRES_PORT=5432 in .env) works
# identically, since the schema/DDL is the same either way. `docker compose
# up db` remains available for anyone who prefers a disposable container
# instead - see ../../DEV_SETUP.md.

# Vite's default dev server port. Overridable/extendable via
# CORS_ALLOWED_ORIGINS in .env without touching this file.
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
