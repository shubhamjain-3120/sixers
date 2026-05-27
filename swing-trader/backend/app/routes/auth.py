from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from kiteconnect import KiteConnect
from app.db.session import get_db
from app.db.models import KiteToken
from app.kite.auth import store_kite_token
from app.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


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

    token = store_kite_token(db, data["access_token"], data.get("public_token"))
    logger.info(f"Kite token stored, expires_at={token.expires_at}")
    return RedirectResponse(url=f"{settings.frontend_base_url}/dashboard")


@router.post("/kite/auto-login")
def kite_auto_login(db: Session = Depends(get_db)):
    from app.kite.auto_login import auto_login
    try:
        token = auto_login(db)
    except Exception as e:
        logger.error(f"Kite auto-login failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    return {"authenticated": True, "expires_at": token.expires_at.isoformat()}


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
