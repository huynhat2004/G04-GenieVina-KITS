import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.config import get_settings
from app.main import app
from scripts.generate_seed import build_dataset, render_sql

ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = 'test-only-secret-with-at-least-32-bytes-long'


@pytest.fixture(scope='session')
def api_database():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run HTTP tests against PostgreSQL')
    schema = 'test_customers_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        test_url = make_conninfo(url, options=f'-csearch_path={schema},public')
        try:
            with psycopg.connect(test_url, autocommit=True) as connection:
                connection.execute((ROOT / 'database/schema.sql').read_text())
                connection.execute(render_sql(build_dataset()))
            with pytest.MonkeyPatch.context() as patch:
                patch.setenv('DATABASE_URL', test_url)
                patch.setenv('JWT_SECRET', TEST_SECRET)
                get_settings.cache_clear()
                yield test_url
        finally:
            get_settings.cache_clear()
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.fixture
def client(api_database):
    with TestClient(app) as instance:
        yield instance
