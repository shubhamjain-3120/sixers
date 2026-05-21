from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from kiteconnect import KiteConnect
from app.db.session import get_db
from app.db.models import KiteToken
from app.config import settings
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
IST = pytz.timezone("Asia/Kolkata")


def _next_6am_ist() -> datetime:
    now_ist = datetime.now(IST)
    next_6am = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)
    if now_ist >= next_6am:
        next_6am += timedelta(days=1)
    return next_6am.astimezone(pytz.utc).replace(tzinfo=None)


@router.get("/kite/login")
def kite_login():
    kite = KiteConnect(api_key=settings.kite_api_key)
    return {"login_url": kite.login_url()}


@router.get("/kite/callback")
def kite_callback(request_token: str = Query(...), db: Session = Depends(get_db)):
    kite = KiteConnect(api_key=settings.kite_api_key)
    try:
        data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
    except Exception as e:
        logger.error(f"Kite session generation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    expires_at = _next_6am_ist()
    token = KiteToken(
        access_token=data["access_token"],
        public_token=data.get("public_token"),
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    logger.info(f"Kite token stored, expires_at={expires_at}")
    return RedirectResponse(url=f"{settings.frontend_base_url}/dashboard")


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    token = db.query(KiteToken).order_by(KiteToken.created_at.desc()).first()
    if not token:
        return {"authenticated": False, "expires_at": None}
    now = datetime.utcnow()
    authenticated = token.expires_at > now
    return {
        "authenticated": authenticated,
        "expires_at": token.expires_at.isoformat() if token else None,
    }
