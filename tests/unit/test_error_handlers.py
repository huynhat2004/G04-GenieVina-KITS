import asyncio
import json

import psycopg
import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.main import database_error, http_error, unexpected_error, validation_error

REQUEST = Request({'type': 'http', 'method': 'GET', 'path': '/api/customers', 'headers': []})
PRIVATE = 'private-database-password-and-query-details'


def response_body(response, status):
    assert response.status_code == status
    body = json.loads(response.body)
    assert set(body) == {'status', 'message', 'data'}
    assert body['status'] == status
    return body


@pytest.mark.parametrize('exception_type,status', [
    (psycopg.errors.UniqueViolation, 409),
    (psycopg.errors.ForeignKeyViolation, 409),
    (psycopg.errors.CheckViolation, 409),
    (psycopg.OperationalError, 503),
    (psycopg.InterfaceError, 503),
    (psycopg.errors.UndefinedTable, 500),
])
def test_database_errors_are_normalized_without_exposing_details(exception_type, status, caplog):
    response = asyncio.run(database_error(REQUEST, exception_type(PRIVATE)))
    body = response_body(response, status)
    assert body['data'] is None
    assert PRIVATE not in response.body.decode()
    assert PRIVATE not in caplog.text


def test_authentication_error_preserves_bearer_challenge():
    response = asyncio.run(http_error(REQUEST, HTTPException(
        401, 'Invalid access token', headers={'WWW-Authenticate': 'Bearer'})))
    assert response_body(response, 401)['message'] == 'Invalid access token'
    assert response.headers['www-authenticate'] == 'Bearer'


def test_validation_error_returns_field_path_without_raw_input_or_context():
    exc = RequestValidationError([{
        'loc': ('body', 'customerCode'), 'msg': 'String should have at most 40 characters',
        'type': 'string_too_long', 'input': PRIVATE, 'ctx': {'private': PRIVATE},
    }], body={'customerCode': PRIVATE})
    response = asyncio.run(validation_error(REQUEST, exc))
    body = response_body(response, 400)
    assert body['data']['errors'] == [{
        'field': 'body.customerCode', 'message': 'String should have at most 40 characters',
    }]
    assert PRIVATE not in response.body.decode()


def test_unexpected_error_does_not_leak_exception_text(caplog):
    response = asyncio.run(unexpected_error(REQUEST, RuntimeError(PRIVATE)))
    assert response_body(response, 500)['message'] == 'Internal server error'
    assert PRIVATE not in response.body.decode()
    assert PRIVATE not in caplog.text
