from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Instrument, Blacklist
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["universe"])


class InstrumentOut(BaseModel):
    symbol: str
    name: Optional[str] = None
    segment: str
    sector: Optional[str] = None
    kite_instrument_token: int

    class Config:
        from_attributes = True


class BlacklistEntry(BaseModel):
    symbol: str
    reason: Optional[str] = None


class BlacklistOut(BaseModel):
    symbol: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/api/universe", response_model=List[InstrumentOut])
def list_universe(db: Session = Depends(get_db)):
    return db.query(Instrument).all()


@router.post("/api/universe/refresh")
def trigger_universe_refresh():
    from app.nse.universe import refresh_universe
    import threading
    t = threading.Thread(target=refresh_universe, daemon=True)
    t.start()
    return {"status": "refresh_started"}


@router.get("/api/blacklist", response_model=List[BlacklistOut])
def list_blacklist(db: Session = Depends(get_db)):
    return db.query(Blacklist).all()


@router.post("/api/blacklist")
def add_blacklist(entry: BlacklistEntry, db: Session = Depends(get_db)):
    existing = db.query(Blacklist).filter(Blacklist.symbol == entry.symbol).first()
    if existing:
        return {"status": "already_blacklisted"}
    bl = Blacklist(symbol=entry.symbol.upper(), reason=entry.reason)
    db.add(bl)
    db.commit()
    return {"status": "added", "symbol": entry.symbol.upper()}


@router.delete("/api/blacklist/{symbol}")
def remove_blacklist(symbol: str, db: Session = Depends(get_db)):
    bl = db.query(Blacklist).filter(Blacklist.symbol == symbol.upper()).first()
    if not bl:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(bl)
    db.commit()
    return {"status": "removed"}
