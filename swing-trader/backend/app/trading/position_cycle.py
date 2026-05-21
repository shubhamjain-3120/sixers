import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Trade, Config, OrderLog
from app.kite.client import RateLimitedKite
from app.kite.gtt import place_single_trail_gtt, modify_trail_gtt
from app.trading.reconcile import reconcile_exit

logger = logging.getLogger(__name__)


@dataclass
class CycleReport:
    positions: int
    trails_engaged: int = 0
    trails_updated: int = 0
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

    # Index GTTs by their trigger_id (meta/tag not supported in this SDK version)
    gtt_by_id = {g["id"]: g for g in gtts}

    cfg = db.query(Config).filter(Config.id == 1).first()
    report = CycleReport(positions=len(positions))

    for p in positions:
        ltp_key = f"NSE:{p.symbol}"
        ltp = ltp_map.get(ltp_key, {}).get("last_price")
        if ltp is None:
            logger.warning(f"No LTP for {p.symbol}")
            continue

        gtt = gtt_by_id.get(p.active_gtt_id) if p.active_gtt_id else None

        # Exit reconciliation
        if gtt and gtt["status"] == "triggered":
            reconcile_exit(db, kite, p, gtt)
            report.exits_reconciled += 1
            continue

        if gtt and gtt["status"] in ("cancelled", "rejected", "expired", "deleted"):
            logger.warning(f"GTT for {p.symbol} trade {p.id} in state {gtt['status']}")
            continue

        # High water mark
        if p.high_water_mark is None or ltp > p.high_water_mark:
            p.high_water_mark = ltp

        target_pct = cfg.target_pct if cfg else 2.0
        trail_dist = cfg.trail_distance_pct if cfg else 1.0
        lock_floor_pct = cfg.trail_lock_floor_pct if cfg else 0.5

        # Initial → Trailing transition
        if p.trailing_state == "initial":
            if ltp >= p.entry_price * (1 + target_pct / 100):
                lock_floor = p.entry_price * (1 + lock_floor_pct / 100)
                hw_based = p.high_water_mark * (1 - trail_dist / 100)
                new_sl = max(lock_floor, hw_based)

                try:
                    kite.delete_gtt(p.active_gtt_id)
                except Exception as e:
                    logger.warning(f"Delete old GTT failed: {e}")

                try:
                    new_gtt_id = place_single_trail_gtt(
                        kite, db, p.id, p.symbol, p.qty,
                        round(new_sl, 1), ltp, p.gtt_tag,
                    )
                    p.active_gtt_id = new_gtt_id
                    p.trailing_state = "trailing"
                    p.current_sl_price = new_sl
                    _log_event(db, p.id, "TRAIL_ENGAGED", {"new_sl": new_sl, "hw": p.high_water_mark, "ltp": ltp})
                    report.trails_engaged += 1
                    logger.info(f"TRAIL_ENGAGED {p.symbol} new_sl={new_sl:.2f} hw={p.high_water_mark:.2f}")
                except Exception as e:
                    logger.error(f"Trail GTT placement failed for {p.symbol}: {e}")

        # Trailing → SL trail-up
        elif p.trailing_state == "trailing":
            lock_floor = p.entry_price * (1 + lock_floor_pct / 100)
            hw_based = p.high_water_mark * (1 - trail_dist / 100)
            candidate_sl = max(lock_floor, hw_based)

            if candidate_sl > (p.current_sl_price or 0) + 0.05:
                try:
                    modify_trail_gtt(
                        kite, db, p.id, p.active_gtt_id,
                        p.symbol, p.qty, round(candidate_sl, 1), ltp,
                    )
                    p.current_sl_price = candidate_sl
                    _log_event(db, p.id, "TRAIL_UPDATED", {"new_sl": candidate_sl, "ltp": ltp})
                    report.trails_updated += 1
                    logger.info(f"TRAIL_UPDATED {p.symbol} new_sl={candidate_sl:.2f}")
                except Exception as e:
                    logger.error(f"Trail GTT modify failed for {p.symbol}: {e}")

        db.commit()

    logger.info(
        f"Position cycle done: {report.positions} open, "
        f"{report.trails_engaged} engaged, {report.trails_updated} updated, "
        f"{report.exits_reconciled} reconciled"
    )
    return report
