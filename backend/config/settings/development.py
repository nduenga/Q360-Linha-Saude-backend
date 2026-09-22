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

# Vite's default port is 5173, but it silently picks the next free one
# (5174, 5175...) whenever 5173 is already taken by another process - a
# real, recurring source of "backend logs 200 but the browser shows a
# generic fetch error" confusion (the CORS preflight itself always
# succeeds; it's the *actual* request that the browser then blocks because
# the concrete port isn't in the allow-list). A regex covering any
# localhost port sidesteps that entirely for local dev - set
# unconditionally (django-cors-headers ORs this together with
# CORS_ALLOWED_ORIGINS, so a value set in .env still works too, it's just
# no longer required).
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:\d+$", r"^http://127\.0\.0\.1:\d+$"]

# Dev-only fallback, same pattern as SECRET_KEY above — never set in
# production (config/settings/production.py raises if this is empty).
CUSTOMER_PORTAL_JWT_SECRET = CUSTOMER_PORTAL_JWT_SECRET or "s01-development-only-portal-secret-change-me"
# No real SMTP configured locally — print emails to the console instead of
# sending them (Django's own, real console backend, not a fake one).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
