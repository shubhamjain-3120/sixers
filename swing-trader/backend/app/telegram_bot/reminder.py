import logging
import requests
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


def send_login_link() -> bool:
    """Send the login reminder. Returns True on success."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured; skipping login reminder")
        return False

    text = (
        "🔐 Kite session expired. Tap to login: "
        f"{settings.app_base_url}/dashboard\n\n"
        "Trading paused until you login. Existing positions are managed by GTTs at Zerodha (safe)."
    )
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": settings.telegram_chat_id, "text": text},
            timeout=10,
        )
        if resp.ok:
            logger.info("Login reminder sent via Telegram")
            return True
        logger.error(f"Telegram send failed: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Telegram send exception: {e}")
        return False


def maybe_send_login_reminder(db) -> bool:
    from app.db.models import KiteToken
    token = db.query(KiteToken).order_by(KiteToken.created_at.desc()).first()
    if token and token.expires_at > datetime.utcnow():
        return False  # still valid
    return send_login_link()
