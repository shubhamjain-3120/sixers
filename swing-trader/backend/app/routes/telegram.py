from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings
import requests
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramSetupRequest(BaseModel):
    bot_token: str


@router.post("/setup")
def telegram_setup(body: TelegramSetupRequest):
    """Get chat_id from the most recent /start message."""
    url = f"https://api.telegram.org/bot{body.bot_token}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not data.get("ok"):
        raise HTTPException(status_code=400, detail="telegram_api_error")

    updates = data.get("result", [])
    if not updates:
        return {"status": "no_messages", "hint": "Send /start to your bot first"}

    latest = updates[-1]
    chat_id = str(latest["message"]["chat"]["id"])
    return {"status": "ok", "chat_id": chat_id}


@router.post("/test")
def telegram_test():
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(status_code=400, detail="telegram_not_configured")
    text = f"✅ Swing Trader test message. Bot is configured correctly.\nApp: {settings.app_base_url}"
    resp = requests.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={"chat_id": settings.telegram_chat_id, "text": text},
        timeout=10,
    )
    if resp.ok:
        return {"status": "sent"}
    raise HTTPException(status_code=500, detail=resp.text)
