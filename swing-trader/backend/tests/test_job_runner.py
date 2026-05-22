"""Tests for the centralized job dispatcher used by /api/system/* routes
and the APScheduler jobs."""
from unittest.mock import patch
import time

from app.jobs import runner


def test_run_job_unknown_returns_false():
    assert runner.run_job("does-not-exist") is False
    assert runner.run_job_async("does-not-exist") is False


def test_run_job_dispatches_to_registered_callable():
    called = {}

    def fake():
        called["yes"] = True

    with patch.dict(runner.JOBS, {"scan": fake}, clear=False):
        assert runner.run_job("scan") is True
    assert called.get("yes") is True


def test_run_job_async_spawns_thread():
    called = {}

    def fake():
        called["yes"] = True

    with patch.dict(runner.JOBS, {"scan": fake}, clear=False):
        assert runner.run_job_async("scan") is True
        # Wait briefly for the daemon thread
        for _ in range(20):
            if called.get("yes"):
                break
            time.sleep(0.01)
    assert called.get("yes") is True


def test_all_expected_jobs_registered():
    for name in ("scan", "position-cycle", "time-stop", "news-classify"):
        assert name in runner.JOBS, f"{name} missing from dispatcher"


def test_with_db_and_kite_skips_when_no_kite():
    """Verifies _with_db_and_kite short-circuits when get_kite_client returns None."""
    called = {}

    def business_fn(db, kite):
        called["yes"] = True

    wrapped = runner._with_db_and_kite(business_fn)

    with patch("app.jobs.runner.SessionLocal", create=True) if False else patch(
        "app.db.session.SessionLocal"
    ) as session_cls, patch("app.kite.client.get_kite_client", return_value=None):
        session_cls.return_value.close = lambda: None
        wrapped()
    assert "yes" not in called
