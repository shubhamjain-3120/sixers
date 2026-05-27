import io
import logging
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Instrument
from app.nse.http import fetch_nse_csv
from app.nse.sectors import build_sector_map
from app.config import settings

logger = logging.getLogger(__name__)

NIFTY50_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"
NIFTY500_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"

HARDCODED_ETFS = [
    {"symbol": "NIFTYCASE", "name": "Zerodha Nifty ETF", "segment": "ETF"},
    {"symbol": "MID150CASE", "name": "Zerodha Nifty Midcap 150 ETF", "segment": "ETF"},
]


def _upsert_instrument(db: Session, symbol: str, name: str, segment: str,
                       sector: str = None, token: int = 0):
    inst = db.query(Instrument).filter(Instrument.symbol == symbol).first()
    if inst:
        inst.name = name
        inst.segment = segment
        if sector:
            inst.sector = sector
        inst.last_refreshed_at = datetime.utcnow()
    else:
        inst = Instrument(
            symbol=symbol, name=name, segment=segment,
            sector=sector, kite_instrument_token=token,
            last_refreshed_at=datetime.utcnow()
        )
        db.add(inst)
    db.commit()


def refresh_universe():
    db = SessionLocal()
    try:
        _do_refresh(db)
    except Exception as e:
        logger.error(f"Universe refresh failed: {e}")
    finally:
        db.close()


def _do_refresh(db: Session):
    logger.info("Starting universe refresh")

    # Upsert ETFs first (always)
    for etf in HARDCODED_ETFS:
        _upsert_instrument(db, etf["symbol"], etf["name"], etf["segment"])
    logger.info("ETFs upserted")

    # Nifty 50 constituents
    try:
        raw = fetch_nse_csv(NIFTY50_CSV_URL)
        df = pd.read_csv(io.BytesIO(raw))
        df.columns = [c.strip() for c in df.columns]
        for _, row in df.iterrows():
            symbol = str(row.get("Symbol", "")).strip()
            name = str(row.get("Company Name", "")).strip()
            if symbol:
                _upsert_instrument(db, symbol, name, "NIFTY50_STOCK")
        logger.info(f"Nifty50 constituents upserted ({len(df)} rows)")
    except Exception as e:
        logger.error(f"Failed to refresh Nifty50 list: {e}")

    # Sector mapping from Nifty 500
    try:
        sector_map = build_sector_map()
        for symbol, sector in sector_map.items():
            inst = db.query(Instrument).filter(Instrument.symbol == symbol).first()
            if inst and sector:
                inst.sector = sector
        db.commit()
        logger.info("Sector map applied")
    except Exception as e:
        logger.error(f"Failed to apply sector map: {e}")

    # Kite instrument token mapping
    try:
        from app.kite.client import get_kite_client
        kite = get_kite_client(db)
        if kite:
            all_instruments = kite.instruments("NSE")
            token_map = {i["tradingsymbol"]: i["instrument_token"] for i in all_instruments}
            for inst in db.query(Instrument).all():
                tok = token_map.get(inst.symbol)
                if tok:
                    inst.kite_instrument_token = tok
            db.commit()
            logger.info("Kite instrument tokens updated")
        else:
            logger.warning("No Kite session; skipping token refresh")
    except Exception as e:
        logger.error(f"Kite instrument token refresh failed: {e}")

    logger.info("Universe refresh complete")
