"""Session-wide test fixtures.

Q360-S1-02 acceptance criteria requires "Testcontainers PostgreSQL": the
foundation migration
(apps/foundation/infrastructure/migrations/0001_foundation_baseline.py)
ports Postgres-only DDL verbatim from ART-012 (schemas, jsonb, CHECK
constraints) and cannot run on SQLite — see OPEN_DECISIONS.md
(S01-PERSISTENCE-001, resolved: PostgreSQL is mandatory wherever the
foundation migration runs).

By default, any test that touches the database starts a disposable
PostgreSQL container for the session (requires a running Docker daemon).
Set Q360_TEST_POSTGRES=true to instead point tests at an already-running
Postgres via the POSTGRES_* env vars (config/settings/base.py) — e.g. the
docker-compose `db` service, or a CI service container.
"""
from __future__ import annotations

import atexit
import os

import pytest


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix):
    if os.environ.get("Q360_TEST_POSTGRES", "").lower() == "true":
        return  # POSTGRES_* env vars already point at a running instance.

    from django.conf import settings
    from testcontainers.community.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    atexit.register(container.stop)

    settings.DATABASES["default"].update(
        {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": container.dbname,
            "USER": container.username,
            "PASSWORD": container.password,
            "HOST": container.get_container_host_ip(),
            "PORT": container.get_exposed_port(container.port),
        }
    )
