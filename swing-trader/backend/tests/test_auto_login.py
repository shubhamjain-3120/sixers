"""Tests for automated daily Kite login via TOTP. All Zerodha calls are mocked."""
import pytest
from unittest.mock import MagicMock, patch

import pyotp

from app.db.models import KiteToken
from app.kite import auto_login as al
from app.kite.auth import _next_6am_ist

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # valid base32 test seed


def _configure_settings(monkeypatch, **overrides):
    for key, val in {
        "kite_user_id": "AB1234",
        "kite_password": "hunter2",
        "kite_totp_secret": TOTP_SECRET,
        "kite_api_key": "test_key",
        "kite_api_secret": "test_secret",
        **overrides,
    }.items():
        monkeypatch.setattr(al.settings, key, val)


def _fake_session(location=None, resp_url=""):
    """Build a mock requests.Session for the login/twofa/connect flow.

    `location` is the 302 redirect Location header from connect/login (where the
    request_token normally lives); `resp_url` is the response's own URL.
    """
    session = MagicMock()

    login_resp = MagicMock()
    login_resp.json.return_value = {"data": {"request_id": "req123"}}
    twofa_resp = MagicMock()
    session.post.side_effect = [login_resp, twofa_resp]

    connect_resp = MagicMock()
    if location is None:
        location = (
            "https://swing-trader-api.fly.dev/api/auth/kite/callback"
            "?request_token=RT123&action=login&status=success"
        )
    connect_resp.headers = {"Location": location}
    connect_resp.url = resp_url
    session.get.return_value = connect_resp
    return session, session.post


class TestAutoLogin:
    def test_success_stores_token(self, db, monkeypatch):
        _configure_settings(monkeypatch)
        session, post = _fake_session()

        fake_kite = MagicMock()
        fake_kite.generate_session.return_value = {
            "access_token": "AT", "public_token": "PT",
        }
        with patch.object(al.requests, "Session", return_value=session), \
             patch.object(al, "KiteConnect", return_value=fake_kite):
            token = al.auto_login(db)

        assert token.access_token == "AT"
        assert token.public_token == "PT"
        assert token.expires_at == _next_6am_ist()
        # persisted
        stored = db.query(KiteToken).order_by(KiteToken.created_at.desc()).first()
        assert stored.access_token == "AT"
        # request_token forwarded to generate_session
        fake_kite.generate_session.assert_called_once_with("RT123", api_secret="test_secret")

    def test_sends_valid_totp(self, db, monkeypatch):
        _configure_settings(monkeypatch)
        session, post = _fake_session()
        fake_kite = MagicMock()
        fake_kite.generate_session.return_value = {"access_token": "AT"}

        with patch.object(al.requests, "Session", return_value=session), \
             patch.object(al, "KiteConnect", return_value=fake_kite):
            al.auto_login(db)

        twofa_call = post.call_args_list[1]
        sent = twofa_call[1]["data"]["twofa_value"]
        assert sent == pyotp.TOTP(TOTP_SECRET).now()
        assert twofa_call[1]["data"]["twofa_type"] == "totp"
        assert twofa_call[1]["data"]["request_id"] == "req123"

    def test_does_not_follow_redirect(self, db, monkeypatch):
        _configure_settings(monkeypatch)
        session, _ = _fake_session()
        fake_kite = MagicMock()
        fake_kite.generate_session.return_value = {"access_token": "AT"}

        with patch.object(al.requests, "Session", return_value=session), \
             patch.object(al, "KiteConnect", return_value=fake_kite):
            al.auto_login(db)

        # connect/login must be fetched with allow_redirects=False so the live
        # callback can't consume the one-time request_token.
        assert session.get.call_args[1]["allow_redirects"] is False

    def test_extracts_request_token_from_response_url(self, db, monkeypatch):
        _configure_settings(monkeypatch)
        # No Location header; token only present in the response URL.
        session, _ = _fake_session(
            location="", resp_url="http://x/cb?request_token=FROMURL&status=success"
        )
        fake_kite = MagicMock()
        fake_kite.generate_session.return_value = {"access_token": "AT"}

        with patch.object(al.requests, "Session", return_value=session), \
             patch.object(al, "KiteConnect", return_value=fake_kite):
            al.auto_login(db)

        fake_kite.generate_session.assert_called_once_with("FROMURL", api_secret="test_secret")

    def test_missing_credentials_raises(self, db, monkeypatch):
        _configure_settings(monkeypatch, kite_totp_secret="")
        with pytest.raises(RuntimeError, match="credentials not configured"):
            al.auto_login(db)

    def test_no_request_token_raises(self, db, monkeypatch):
        _configure_settings(monkeypatch)
        session, _ = _fake_session(location="", resp_url="http://x/dashboard")
        with patch.object(al.requests, "Session", return_value=session):
            with pytest.raises(RuntimeError, match="request_token not found"):
                al.auto_login(db)


class TestJobAutoLogin:
    def test_failure_sends_telegram_alert(self, monkeypatch):
        from app.jobs import scheduler

        monkeypatch.setattr("app.db.session.SessionLocal", lambda: MagicMock())
        monkeypatch.setattr(al, "auto_login", MagicMock(side_effect=RuntimeError("boom")))
        sent = MagicMock(return_value=True)
        monkeypatch.setattr("app.telegram_bot.reminder.send_alert", sent)

        scheduler.job_auto_login()

        sent.assert_called_once()
        assert "boom" in sent.call_args[0][0]
