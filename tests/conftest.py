from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Every test gets its own throwaway STORAGE_DIR + fixed test API keys/
    JWT secret, and get_settings()/get_storage()'s lru_cache is cleared so
    each test doesn't see another test's settings or files."""
    tmp_dir = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp_dir)
    monkeypatch.setenv("APP_API_KEYS", "test-api-key")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    import app.core.storage as storage_module
    from app.core.config import get_settings

    get_settings.cache_clear()
    storage_module._storage = None
    yield
    get_settings.cache_clear()
    storage_module._storage = None


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
