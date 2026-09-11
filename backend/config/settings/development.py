from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# S01-PERSISTENCE-001 (see OPEN_DECISIONS.md): PostgreSQL is mandatory, not
# optional, in every environment. The foundation migration
# (apps/foundation/infrastructure/migrations/0001_foundation_baseline.py)
# ports ART-012 DDL verbatim (schemas, jsonb, CHECK constraints) and cannot
# run on SQLite — a SQLite fallback would let `migrate` "succeed" against a
# schema that silently diverges from ART-005/ART-012, which is exactly what
# DOC-000 s3 P-08 forbids. Run `docker compose up db` for a local instance.
