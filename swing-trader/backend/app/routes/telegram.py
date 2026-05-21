from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.config import settings
from app.db.session import get_db
from app.db.models import Config
import requests
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramSetupRequest(BaseModel):
    bot_token: str


def _get_or_create_config(db: Session) -> Config:
    cfg = db.query(Config).first()
    if not cfg:
        cfg = Config(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.post("/setup")
def telegram_setup(body: TelegramSetupRequest, db: Session = Depends(get_db)):
    """Discover chat_id via getUpdates and persist both token and chat_id to DB."""
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

    cfg = _get_or_create_config(db)
    cfg.telegram_bot_token = body.bot_token
    cfg.telegram_chat_id = chat_id
    db.commit()

    logger.info(f"Telegram credentials saved: chat_id={chat_id}")
    return {"status": "ok", "chat_id": chat_id}


@router.post("/test")
def telegram_test(db: Session = Depends(get_db)):
    """Send a test message using DB-stored credentials (falls back to env vars)."""
    cfg = db.query(Config).first()
    bot_token = (cfg and cfg.telegram_bot_token) or settings.telegram_bot_token
    chat_id = (cfg and cfg.telegram_chat_id) or settings.telegram_chat_id

    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="telegram_not_configured")

    text = f"✅ Swing Trader test message. Bot is configured correctly.\nApp: {settings.app_base_url}"
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    if resp.ok:
        return {"status": "sent"}
    raise HTTPException(status_code=500, detail=resp.text)
