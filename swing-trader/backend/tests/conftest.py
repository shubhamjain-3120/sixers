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
