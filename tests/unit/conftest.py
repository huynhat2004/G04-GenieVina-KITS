import pytest


@pytest.fixture(autouse=True)
def forbid_database_connections(monkeypatch):
    """A unit test must never silently depend on a running PostgreSQL server."""
    def fail_connection(*args, **kwargs):
        pytest.fail('Unit tests must not connect to PostgreSQL')

    monkeypatch.setattr('psycopg.connect', fail_connection)
