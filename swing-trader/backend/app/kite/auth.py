from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import KiteToken
from app.db.session import get_db
from datetime import datetime
from typing import Optional


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
