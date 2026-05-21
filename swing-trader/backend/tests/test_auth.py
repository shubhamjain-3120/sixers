"""Tests for Kite auth flow (M-2)."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.models import Base, KiteToken
from app.db.session import get_db

# ── In-memory SQLite for tests ────────────────────────────────────────────────
# StaticPool: all sessions share a single connection, so one in-memory DB is used.

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_token(db, expires_delta_hours: float):
    tok = KiteToken(
        access_token="test_token",
        public_token="test_public",
        expires_at=datetime.utcnow() + timedelta(hours=expires_delta_hours),
    )
    db.add(tok)
    db.commit()
    return tok


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_status_no_token(client):
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated"] is False
    assert data["expires_at"] is None


def test_status_with_valid_token(client, db):
    _insert_token(db, expires_delta_hours=8)
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated"] is True
    assert data["expires_at"] is not None


def test_status_with_expired_token(client, db):
    _insert_token(db, expires_delta_hours=-1)
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated"] is False


def test_login_url_returned(client):
    r = client.get("/api/auth/kite/login")
    assert r.status_code == 200
    data = r.json()
    assert "login_url" in data
    assert "kite.zerodha.com" in data["login_url"]


def test_require_auth_dependency_rejects_unauthenticated(client):
    # Trades endpoint requires auth — should 401 with no token
    r = client.post("/api/trades", json={"symbol": "HDFCBANK"})
    assert r.status_code == 401
    assert r.json()["detail"] == "kite_session_expired"


def test_require_auth_dependency_allows_authenticated(client, db):
    # With a valid token the dependency passes (the route itself may 400/422 for
    # other reasons, but it won't 401)
    _insert_token(db, expires_delta_hours=8)
    r = client.post("/api/trades", json={"symbol": "HDFCBANK"})
    assert r.status_code != 401
