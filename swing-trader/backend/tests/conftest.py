"""Shared pytest fixtures. Each test gets a fresh schema in the in-memory
SQLite engine defined in tests/_db.py."""
import pytest

from tests._db import Base, TestingSessionLocal, engine


@pytest.fixture(autouse=True)
def _create_drop_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _block_real_kite(monkeypatch):
    """Prevent any test from accidentally reaching real Kite/Zerodha APIs."""
    import app.kite.client as kc

    def _boom(*a, **kw):
        raise RuntimeError(
            "Real Kite call attempted in test — mock it via _kite_fake.py."
        )

    monkeypatch.setattr(kc, "get_kite_client", _boom)


@pytest.fixture(autouse=True)
def _block_real_env(monkeypatch):
    """Override sensitive env vars so no real credentials leak into tests."""
    monkeypatch.setenv("KITE_API_KEY", "test_key")
    monkeypatch.setenv("KITE_API_SECRET", "test_secret")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
