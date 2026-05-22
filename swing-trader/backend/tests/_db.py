"""Shared in-memory SQLite engine for the test suite.

StaticPool keeps all sessions on a single connection, so one in-memory DB
is shared across the test process. Tables are created/dropped per test via
the autouse fixture in conftest.py.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db

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


__all__ = ["engine", "TestingSessionLocal", "Base", "get_db", "override_get_db"]
