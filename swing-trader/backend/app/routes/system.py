from fastapi import APIRouter
import logging

from app.jobs.runner import run_job_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/scan")
def trigger_scan():
    run_job_async("scan")
    return {"status": "scan_started"}


@router.post("/position-cycle")
def trigger_position_cycle():
    run_job_async("position-cycle")
    return {"status": "cycle_started"}


@router.post("/time-stop")
def trigger_time_stop():
    run_job_async("time-stop")
    return {"status": "time_stop_started"}


@router.post("/news-classify")
def trigger_news_classify():
    run_job_async("news-classify")
    return {"status": "classification_started"}


@router.post("/login-reminder")
def trigger_login_reminder():
    """Force-send the Telegram login reminder regardless of token state. For testing."""
    from app.telegram_bot.reminder import send_login_link
    from app.db.session import SessionLocal
    from app.db.models import Config
    from app.config import settings
    db = SessionLocal()
    try:
        cfg = db.query(Config).first()
        bot_token = (cfg and cfg.telegram_bot_token) or settings.telegram_bot_token
        chat_id = (cfg and cfg.telegram_chat_id) or settings.telegram_chat_id
        sent = send_login_link(bot_token, chat_id)
        return {"status": "sent" if sent else "failed_or_not_configured"}
    finally:
        db.close()


@router.get("/health")
def health():
    return {"status": "ok"}
