import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Trade, Config, OrderLog
from app.kite.client import RateLimitedKite
from app.trading.reconcile import reconcile_exit

logger = logging.getLogger(__name__)


@dataclass
class CycleReport:
    positions: int
    exits_reconciled: int = 0


def _log_event(db: Session, trade_id: int, action: str, detail: dict):
    import json
    db.add(OrderLog(
        trade_id=trade_id,
        action=action,
        status="info",
        raw_response=json.dumps(detail),
    ))


def run_cycle(db: Session, kite: RateLimitedKite) -> CycleReport:
    positions = db.query(Trade).filter(Trade.status == "OPEN").all()
    if not positions:
        return CycleReport(positions=0)

    symbols = [f"NSE:{p.symbol}" for p in positions]
    try:
        ltp_map = kite.ltp(symbols)
    except Exception as e:
        logger.error(f"LTP fetch failed in position cycle: {e}")
        return CycleReport(positions=len(positions))

    try:
        gtts = kite.get_gtts()
    except Exception as e:
        logger.error(f"GTT fetch failed in position cycle: {e}")
        return CycleReport(positions=len(positions))

    # Primary: index by meta.tag (set on every GTT we place)
    gtt_by_tag: dict = {
        g["meta"]["tag"]: g
        for g in gtts
        if g.get("meta") and g["meta"].get("tag", "").startswith("trade_")
    }
    # Fallback: index by numeric id for GTTs placed before tagging was added
    gtt_by_id = {g["id"]: g for g in gtts}

    cfg = db.query(Config).filter(Config.id == 1).first()
    report = CycleReport(positions=len(positions))

    for p in positions:
        ltp_key = f"NSE:{p.symbol}"
        ltp = ltp_map.get(ltp_key, {}).get("last_price")
        if ltp is None:
            logger.warning(f"No LTP for {p.symbol}")
            continue

        # Tag-based lookup first; fall back to ID for legacy records
        gtt = gtt_by_tag.get(p.gtt_tag) or (gtt_by_id.get(p.active_gtt_id) if p.active_gtt_id else None)

        # Exit reconciliation
        if gtt and gtt["status"] == "triggered":
            reconcile_exit(db, kite, p, gtt)
            report.exits_reconciled += 1
            continue

        if gtt and gtt["status"] in ("cancelled", "rejected", "expired", "deleted"):
            logger.warning(f"GTT for {p.symbol} trade {p.id} in state {gtt['status']}")
            continue

        db.commit()

    logger.info(
        f"Position cycle done: {report.positions} open, "
        f"{report.exits_reconciled} reconciled"
    )
    return report
