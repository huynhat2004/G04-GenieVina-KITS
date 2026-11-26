from typing import Annotated

import hashlib

import jwt
import psycopg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import get_connection
from app.models import Principal

Database = Annotated[psycopg.Connection, Depends(get_connection, scope='function')]
bearer = HTTPBearer(auto_error=False, description='JWT HS256: sub = member ID (string), exp required.')


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    connection: Database,
) -> Principal:
    unauthorized = HTTPException(401, 'Invalid or missing access token', headers={'WWW-Authenticate': 'Bearer'})
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret,
                            algorithms=['HS256'], options={'require': ['sub', 'exp']})
        subject = claims['sub']
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
            raise unauthorized
        member_id = int(subject)
        if not 0 < member_id <= 9223372036854775807:
            raise unauthorized
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    member = connection.execute('''SELECT id, role FROM members WHERE id = %s AND NOT EXISTS
        (SELECT 1 FROM revoked_tokens WHERE token_hash = %s AND expires_at > CURRENT_TIMESTAMP)''',
        (member_id, hashlib.sha256(credentials.credentials.encode()).hexdigest())).fetchone()
    if member is None:
        raise unauthorized
    return Principal(**member)


def require_roles(*roles: str):
    def check(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in roles:
            raise HTTPException(403, 'Insufficient permissions')
        return principal
    return check
