from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


def get_connection() -> Iterator[psycopg.Connection]:
    # Use function-scoped Depends: commit/rollback finishes BEFORE sending a response.
    with psycopg.connect(get_settings().database_url, row_factory=dict_row, connect_timeout=5) as connection:
        yield connection
