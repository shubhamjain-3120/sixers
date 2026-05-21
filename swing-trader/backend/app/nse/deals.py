import io
import logging
from datetime import date, datetime
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db.session import SessionLocal
from app.db.models import BlockDeal
from app.nse.http import fetch_nse_csv

logger = logging.getLogger(__name__)
BLOCK_CSV_URL = "https://nsearchives.nseindia.com/content/equities/block.csv"
BULK_CSV_URL = "https://nsearchives.nseindia.com/content/equities/bulk.csv"


def _parse_deal_date(s: str) -> date:
    try:
        return datetime.strptime(s.strip(), "%d-%b-%Y").date()
    except Exception:
        return date.today()


def _ingest_deals(db: Session, url: str, source: str):
    try:
        raw = fetch_nse_csv(url)
        df = pd.read_csv(io.BytesIO(raw))
        df.columns = [c.strip() for c in df.columns]
        col_map = {
            "Date": "deal_date",
            "Symbol": "symbol",
            "Client Name": "client_name",
            "Buy/Sell": "deal_type",
            "Quantity Traded": "quantity",
            "Trade Price /Wght. Avg. Price": "price",
        }
        for _, row in df.iterrows():
            try:
                deal_date = _parse_deal_date(str(row.get("Date", "")))
                symbol = str(row.get("Symbol", "")).strip().upper()
                client_name = str(row.get("Client Name", "")).strip()
                deal_type_raw = str(row.get("Buy/Sell", "")).strip().upper()
                deal_type = "BUY" if "BUY" in deal_type_raw else "SELL"
                qty_raw = str(row.get("Quantity Traded", "0")).replace(",", "").strip()
                qty = int(float(qty_raw)) if qty_raw else 0
                price_raw = str(row.get("Trade Price /Wght. Avg. Price", "0")).replace(",", "").strip()
                price = float(price_raw) if price_raw else 0.0

                existing = (
                    db.query(BlockDeal)
                    .filter(
                        BlockDeal.deal_date == deal_date,
                        BlockDeal.symbol == symbol,
                        BlockDeal.client_name == client_name,
                        BlockDeal.quantity == qty,
                    )
                    .first()
                )
                if not existing:
                    bd = BlockDeal(
                        deal_date=deal_date, symbol=symbol, client_name=client_name,
                        deal_type=deal_type, quantity=qty, price=price, source=source,
                    )
                    db.add(bd)
            except Exception as e:
                logger.warning(f"Skipping deal row: {e}")
        db.commit()
        logger.info(f"{source} deals ingested")
    except Exception as e:
        logger.error(f"Failed to fetch {source} deals from {url}: {e}")


def fetch_deals():
    db = SessionLocal()
    try:
        _ingest_deals(db, BLOCK_CSV_URL, "block")
        _ingest_deals(db, BULK_CSV_URL, "bulk")
    finally:
        db.close()
