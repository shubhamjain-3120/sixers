from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import KiteToken
from app.db.session import get_db
from datetime import datetime, timedelta
from typing import Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")


def _next_6am_ist() -> datetime:
    now_ist = datetime.now(IST)
    next_6am = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)
    if now_ist >= next_6am:
        next_6am += timedelta(days=1)
    return next_6am.astimezone(pytz.utc).replace(tzinfo=None)


def store_kite_token(db: Session, access_token: str, public_token: Optional[str] = None) -> KiteToken:
    token = KiteToken(
        access_token=access_token,
        public_token=public_token,
        expires_at=_next_6am_ist(),
    )
    db.add(token)
    db.commit()
    return token


def get_valid_token(db: Session) -> Optional[KiteToken]:
    token = db.query(KiteToken).order_by(KiteToken.created_at.desc()).first()
    if token and token.expires_at > datetime.utcnow():
        return token
    return None


def require_kite_auth(db: Session = Depends(get_db)) -> KiteToken:
    token = get_valid_token(db)
    if not token:
        raise HTTPException(status_code=401, detail="kite_session_expired")
    return token
