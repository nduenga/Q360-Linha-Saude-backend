import pytest
from django.db import connection


@pytest.mark.django_db
def test_postgresql_connection():
    # S01-PERSISTENCE-001: PostgreSQL is mandatory in every environment
    # (tests/conftest.py provisions it via Testcontainers, or via
    # Q360_TEST_POSTGRES=true pointing at an already-running instance) —
    # there is no SQLite fallback to skip against.
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
