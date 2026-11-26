from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import hashlib

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import get_principal, require_roles
from app.config import Settings
from app.models import Principal

SECRET = 'unit-test-secret-at-least-32-bytes-long'


def credentials(claims=None, *, key=SECRET, algorithm='HS256'):
    if claims is None:
        claims = {'sub': '2', 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials=jwt.encode(claims, key, algorithm=algorithm))


@pytest.fixture
def connection(monkeypatch):
    monkeypatch.setattr('app.auth.get_settings', lambda: Settings('unused', SECRET))
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = {'id': 2, 'role': 'OPERATOR'}
    return connection


def assert_unauthorized(credential, connection):
    with pytest.raises(HTTPException) as exc:
        get_principal(credential, connection)
    assert exc.value.status_code == 401
    assert exc.value.headers == {'WWW-Authenticate': 'Bearer'}


def test_valid_token_loads_current_member_and_uses_parameterized_query(connection):
    credential = credentials()
    result = get_principal(credential, connection)
    assert result == Principal(id=2, role='OPERATOR')
    query, parameters = connection.execute.call_args.args
    assert '%s' in query
    assert parameters == (2, hashlib.sha256(credential.credentials.encode()).hexdigest())


def test_role_claim_does_not_override_database_permissions(connection):
    token = credentials({'sub': '2', 'exp': 9999999999, 'role': 'ADMIN'})
    assert get_principal(token, connection).role == 'OPERATOR'


def test_deleted_member_cannot_use_an_unexpired_token(connection):
    connection.execute.return_value.fetchone.return_value = None
    assert_unauthorized(credentials(), connection)


@pytest.mark.parametrize('subject', ['0', '-1', 'not-an-id', '1 OR 1=1', '１２', '9223372036854775808', 2, None])
def test_invalid_member_identifiers_are_rejected_before_database_access(connection, subject):
    assert_unauthorized(credentials({'sub': subject, 'exp': 9999999999}), connection)
    connection.execute.assert_not_called()


@pytest.mark.parametrize('claims', [
    {'sub': '2'}, {'exp': 9999999999},
    {'sub': '2', 'exp': 1}, {'sub': '2', 'exp': 'invalid'},
    {'sub': '2', 'exp': 9999999999, 'nbf': 9999999998},
])
def test_missing_expired_or_not_yet_valid_claims(connection, claims):
    assert_unauthorized(credentials(claims), connection)
    connection.execute.assert_not_called()


def test_missing_and_malformed_token(connection):
    for credential in [None, HTTPAuthorizationCredentials(scheme='Bearer', credentials='not-a-jwt')]:
        assert_unauthorized(credential, connection)
    connection.execute.assert_not_called()


@pytest.mark.parametrize('key,algorithm', [
    ('wrong-signing-key-with-at-least-32-bytes', 'HS256'),
    (SECRET * 2, 'HS384'), (None, 'none'),
])
def test_wrong_signature_or_algorithm_is_rejected(connection, key, algorithm):
    assert_unauthorized(credentials(key=key, algorithm=algorithm), connection)
    connection.execute.assert_not_called()


@pytest.mark.parametrize('allowed', [
    ('ADMIN',), ('ADMIN', 'OPERATOR'), ('ADMIN', 'OPERATOR', 'VIEWER'),
])
@pytest.mark.parametrize('role', ['ADMIN', 'OPERATOR', 'VIEWER'])
def test_read_write_delete_permission_matrix(allowed, role):
    principal = Principal(id=1, role=role)
    check = require_roles(*allowed)
    if role in allowed:
        assert check(principal) == principal
    else:
        with pytest.raises(HTTPException) as exc:
            check(principal)
        assert exc.value.status_code == 403
