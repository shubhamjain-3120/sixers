"""Tests for M-11: Telegram login reminder."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.db.models import Config, KiteToken
from app.telegram_bot.reminder import send_login_link, maybe_send_login_reminder


@pytest.fixture
def cfg(db):
    config = Config(
        id=1,
        telegram_bot_token="test-bot-token",
        telegram_chat_id="123456789",
    )
    db.add(config)
    db.commit()
    return config


def _make_token(db, expired: bool):
    if expired:
        expires_at = datetime.utcnow() - timedelta(days=1)
    else:
        expires_at = datetime.utcnow() + timedelta(hours=12)
    token = KiteToken(access_token="tok", expires_at=expires_at)
    db.add(token)
    db.commit()
    return token


# ── send_login_link ───────────────────────────────────────────────────────────

class TestSendLoginLink:
    def test_sends_message_with_provided_credentials(self):
        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            result = send_login_link("bot123", "chat456")

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "bot123" in call_kwargs[0][0]
        payload = call_kwargs[1]["json"]
        assert payload["chat_id"] == "chat456"
        assert "Kite session expired" in payload["text"]

    def test_returns_false_when_no_credentials(self):
        with patch("app.telegram_bot.reminder.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""
            mock_settings.telegram_chat_id = ""
            result = send_login_link()
        assert result is False

    def test_returns_false_on_api_failure(self):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.text = "Unauthorized"
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp):
            result = send_login_link("bad-token", "chat456")
        assert result is False

    def test_returns_false_on_exception(self):
        with patch("app.telegram_bot.reminder.requests.post", side_effect=Exception("timeout")):
            result = send_login_link("bot123", "chat456")
        assert result is False


# ── maybe_send_login_reminder ─────────────────────────────────────────────────

class TestMaybeSendLoginReminder:
    def test_skips_when_token_still_valid(self, db, cfg):
        _make_token(db, expired=False)
        with patch("app.telegram_bot.reminder.requests.post") as mock_post:
            result = maybe_send_login_reminder(db)
        assert result is False
        mock_post.assert_not_called()

    def test_sends_when_token_expired(self, db, cfg):
        _make_token(db, expired=True)
        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            result = maybe_send_login_reminder(db)
        assert result is True
        mock_post.assert_called_once()

    def test_sends_when_no_token_row_exists(self, db, cfg):
        # No token row at all — treat as expired
        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            result = maybe_send_login_reminder(db)
        assert result is True
        mock_post.assert_called_once()

    def test_uses_db_credentials_over_env(self, db):
        # Config in DB has different credentials than env
        config = Config(id=1, telegram_bot_token="db-bot", telegram_chat_id="db-chat")
        db.add(config)
        db.commit()
        _make_token(db, expired=True)

        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            with patch("app.telegram_bot.reminder.settings") as mock_settings:
                mock_settings.telegram_bot_token = "env-bot"
                mock_settings.telegram_chat_id = "env-chat"
                mock_settings.app_base_url = "http://localhost:8000"
                maybe_send_login_reminder(db)

        url = mock_post.call_args[0][0]
        assert "db-bot" in url
        assert mock_post.call_args[1]["json"]["chat_id"] == "db-chat"

    def test_falls_back_to_env_when_db_empty(self, db):
        # No Config row, env vars set
        _make_token(db, expired=True)
        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            with patch("app.telegram_bot.reminder.settings") as mock_settings:
                mock_settings.telegram_bot_token = "env-bot"
                mock_settings.telegram_chat_id = "env-chat"
                mock_settings.app_base_url = "http://localhost:8000"
                result = maybe_send_login_reminder(db)
        assert result is True
        url = mock_post.call_args[0][0]
        assert "env-bot" in url

    def test_skips_when_no_credentials_anywhere(self, db):
        _make_token(db, expired=True)
        with patch("app.telegram_bot.reminder.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""
            mock_settings.telegram_chat_id = ""
            result = maybe_send_login_reminder(db)
        assert result is False

    def test_reminder_message_contains_dashboard_link(self, db, cfg):
        _make_token(db, expired=True)
        mock_resp = MagicMock()
        mock_resp.ok = True
        with patch("app.telegram_bot.reminder.requests.post", return_value=mock_resp) as mock_post:
            with patch("app.telegram_bot.reminder.settings") as mock_settings:
                mock_settings.telegram_bot_token = ""
                mock_settings.telegram_chat_id = ""
                mock_settings.app_base_url = "http://myserver:8000"
                maybe_send_login_reminder(db)

        payload = mock_post.call_args[1]["json"]
        assert "/dashboard" in payload["text"]
        assert "GTTs at Zerodha" in payload["text"]
