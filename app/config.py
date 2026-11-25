import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str


@lru_cache
def get_settings() -> Settings:
    database_url = os.environ.get('DATABASE_URL', '')
    jwt_secret = os.environ.get('JWT_SECRET', '')
    if not database_url:
        raise RuntimeError('DATABASE_URL is required')
    if len(jwt_secret.encode()) < 32:
        raise RuntimeError('JWT_SECRET must contain at least 32 bytes')
    return Settings(database_url, jwt_secret)
