import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.kite.client import get_kite_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/funds", tags=["funds"])


class FundsResponse(BaseModel):
    kite_funds_available: Optional[float] = None


@router.get("", response_model=FundsResponse)
def get_funds(db: Session = Depends(get_db)):
    kite = get_kite_client(db)
    if not kite:
        return FundsResponse(kite_funds_available=None)
    try:
        data = kite.margins("equity")
        net = data.get("net") or data.get("available", {}).get("cash")
        return FundsResponse(kite_funds_available=net)
    except Exception:
        logger.exception("Failed to fetch Kite margins")
        return FundsResponse(kite_funds_available=None)
