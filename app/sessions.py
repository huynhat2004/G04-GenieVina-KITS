"""Password login and persistent access-token revocation."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

from app.auth import Database, bearer, get_principal
from app.config import get_settings
from app.models import Envelope, ErrorEnvelope, Principal
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix='/api/auth', tags=['Authentication'], responses={c: {'model': ErrorEnvelope} for c in (400,401,500,503)})

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=1,max_length=1024)

class TokenOut(BaseModel):
    accessToken: str
    tokenType: str = 'bearer'
    expiresIn: int = 1800

# Use the same cost on unknown accounts to avoid a fast account-existence oracle.
DUMMY_HASH = 'pbkdf2_sha256$600000$dummy-login-salt$' + base64.b64encode(bytes(32)).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or not 100000 <= int(rounds) <= 2000000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds))
        return hmac.compare_digest(actual, base64.b64decode(expected, validate=True))
    except (ValueError, TypeError):
        return False

@router.post('/login', response_model=Envelope[TokenOut], summary='Login with member email and password')
def login(body: LoginRequest, connection: Database):
    member = connection.execute('SELECT id,password_hash FROM members WHERE lower(email)=lower(%s)',(body.email.strip(),)).fetchone()
    valid = verify_password(body.password, member['password_hash'] if member else DUMMY_HASH)
    if not member or not valid:
        raise HTTPException(401,'Invalid email or password',headers={'WWW-Authenticate':'Bearer'})
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub':str(member['id']),'iat':now,'exp':now+timedelta(minutes=30),'jti':secrets.token_hex(24)},
                       get_settings().jwt_secret,algorithm='HS256')
    return {'status':200,'message':'success','data':{'accessToken':token,'tokenType':'bearer','expiresIn':1800}}

@router.post('/logout', response_model=Envelope[None], summary='Revoke the current JWT until expiry')
def logout(connection: Database, principal: Annotated[Principal, Depends(get_principal)],
           credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    token = credentials.credentials
    claims = jwt.decode(token,get_settings().jwt_secret,algorithms=['HS256'],options={'require':['sub','exp']})
    connection.execute('INSERT INTO revoked_tokens(token_hash,expires_at) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                       (hashlib.sha256(token.encode()).hexdigest(),datetime.fromtimestamp(claims['exp'],timezone.utc)))
    return {'status':200,'message':'success','data':None}
