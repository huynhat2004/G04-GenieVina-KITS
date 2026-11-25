import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('JWT_SECRET', raising=False)
    yield
    get_settings.cache_clear()


def test_database_url_is_required(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'X' * 32)
    with pytest.raises(RuntimeError, match='DATABASE_URL is required'):
        get_settings()


@pytest.mark.parametrize('secret', ['', 'X' * 31])
def test_missing_or_short_signing_secret_prevents_startup(monkeypatch, secret):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/test')
    monkeypatch.setenv('JWT_SECRET', secret)
    with pytest.raises(RuntimeError, match='at least 32 bytes'):
        get_settings()


def test_minimum_length_signing_secret_is_accepted(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/test')
    monkeypatch.setenv('JWT_SECRET', 'X' * 32)
    settings = get_settings()
    assert settings.database_url == 'postgresql://localhost/test'
    assert settings.jwt_secret == 'X' * 32
