import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import Trade, Config, Instrument, DailyScan
from app.kite.client import get_kite_client
from app.kite.orders import log_order, wait_for_fill
from app.kite.gtt import place_oco_gtt
from app.trading.stops import compute_stop

logger = logging.getLogger(__name__)


def execute_entry(db: Session, symbol: str, badge: Optional[str] = None, llm_verdict: Optional[str] = None, custom_capital: Optional[float] = None) -> Optional[dict]:
    kite = get_kite_client(db)
    if not kite:
        raise RuntimeError("No Kite session")

    cfg = db.query(Config).filter(Config.id == 1).first()
    inst = db.query(Instrument).filter(Instrument.symbol == symbol).first()

    # Compute qty
    capital_for_trade = custom_capital if custom_capital and custom_capital > 0 else cfg.total_capital_inr * cfg.nifty50_alloc_pct / 100
    ltp_data = kite.ltp([f"NSE:{symbol}"])
    ltp = ltp_data.get(f"NSE:{symbol}", {}).get("last_price")
    if not ltp or ltp <= 0:
        raise ValueError("invalid_ltp")
    qty = int(capital_for_trade // ltp)
    if qty < 1:
        raise ValueError("insufficient_capital")

    limit_price = round(ltp * 1.001, 1)
    gtt_tag = f"trade_{uuid.uuid4().hex[:12]}"

    # Place limit buy
    try:
        order_id = kite.place_order(
            variety="regular",
            exchange="NSE",
            tradingsymbol=symbol,
            transaction_type="BUY",
            quantity=qty,
            order_type="LIMIT",
            price=limit_price,
            product="CNC",
            validity="DAY",
        )
        logger.info(f"Placed buy order {order_id} for {symbol} qty={qty} @ {limit_price}")
    except Exception as e:
        logger.error(f"Buy order placement failed for {symbol}: {e}")
        raise

    log_order(db, None, "PLACE_BUY", "placed", kite_order_id=str(order_id))

    # Poll for fill
    filled_order = wait_for_fill(kite, str(order_id), timeout_seconds=300)

    # On timeout with no fill at all
    if not filled_order or filled_order.get("filled_quantity", 0) == 0:
        try:
            kite.cancel_order("regular", str(order_id))
        except Exception as e:
            logger.warning(f"Cancel failed: {e}")
        return None

    fill_price = filled_order["average_price"]
    filled_qty = filled_order["filled_quantity"]
    is_partial = filled_order["status"] != "COMPLETE"

    # On partial fill: cancel the remainder, then proceed with what filled
    if is_partial:
        logger.warning(f"Partial fill for {symbol}: filled {filled_qty} of {qty} @ {fill_price}")
        try:
            kite.cancel_order("regular", str(order_id))
        except Exception as e:
            logger.warning(f"Cancel of partial remainder failed: {e}")

    # Capture both scores and ATR from the most recent scan.
    latest_scan = (
        db.query(DailyScan)
        .filter(DailyScan.symbol == symbol)
        .order_by(DailyScan.scan_date.desc())
        .first()
    )
    pullback_score = latest_scan.score if latest_scan else None
    shubham_score = latest_scan.shubham_score if latest_scan else None

    target_price = round(fill_price * (1 + cfg.target_pct / 100), 1)
    sl_price, sl_pct, atr_pct = compute_stop(
        fill_price, latest_scan.atr_14 if latest_scan else None, cfg
    )

    # Create trade row
    trade = Trade(
        symbol=symbol,
        segment=inst.segment if inst else "NIFTY50_STOCK",
        badge_at_entry=badge,
        llm_verdict_at_entry=llm_verdict,
        pullback_score_at_entry=pullback_score,
        shubham_score_at_entry=shubham_score,
        ltp_at_entry=latest_scan.ltp if latest_scan else None,
        rsi_at_entry=latest_scan.rsi_14 if latest_scan else None,
        pct_below_20d_high_at_entry=latest_scan.pct_below_20d_high if latest_scan else None,
        pct_below_50d_high_at_entry=latest_scan.pct_below_50d_high if latest_scan else None,
        dist_from_20dma_at_entry=latest_scan.dist_from_20dma_pct if latest_scan else None,
        dist_from_50dma_at_entry=latest_scan.dist_from_50dma_pct if latest_scan else None,
        volume_ratio_at_entry=latest_scan.volume_ratio if latest_scan else None,
        swing_low_at_entry=latest_scan.swing_low_30d if latest_scan else None,
        swing_high_at_entry=latest_scan.swing_high_30d if latest_scan else None,
        pivot_support_at_entry=latest_scan.pivot_support if latest_scan else None,
        pivot_resistance_at_entry=latest_scan.pivot_resistance if latest_scan else None,
        green_after_red_at_entry=latest_scan.green_after_red if latest_scan else None,
        entry_date=datetime.utcnow(),
        entry_price=fill_price,
        qty=filled_qty,
        capital_deployed=fill_price * filled_qty,
        initial_target_price=target_price,
        initial_sl_price=sl_price,
        sl_pct_at_entry=sl_pct,
        atr_pct_at_entry=atr_pct,
        gtt_tag=gtt_tag,
        status="OPEN",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    log_order(db, trade.id, "PLACE_BUY", "filled",
              kite_order_id=str(order_id),
              raw_response=str(filled_order))

    # Place OCO GTT
    try:
        gtt_id = place_oco_gtt(
            kite, db, trade.id, symbol, filled_qty,
            sl_price, target_price, fill_price, gtt_tag,
        )
        trade.active_gtt_id = gtt_id
        db.commit()
        logger.info(f"OCO GTT {gtt_id} placed for trade {trade.id}")
    except Exception as e:
        logger.error(f"GTT placement failed for trade {trade.id}: {e}")
        trade.status = "FAILED"
        trade.notes = f"GTT placement failed: {e}"
        db.commit()
        raise

    return {
        "trade_id": trade.id,
        "fill_price": fill_price,
        "qty": filled_qty,
        "target_price": target_price,
        "sl_price": sl_price,
        "gtt_id": gtt_id,
        "status": "filled",
    }


def execute_force_exit(db: Session, trade: Trade):
    kite = get_kite_client(db)
    if not kite:
        raise RuntimeError("No Kite session")

    if trade.active_gtt_id:
        try:
            kite.delete_gtt(trade.active_gtt_id)
            log_order(db, trade.id, "CANCEL_GTT", "cancelled", kite_gtt_id=trade.active_gtt_id)
        except Exception as e:
            logger.warning(f"GTT cancel on force exit: {e}")

    # Kite API does not allow market orders without market protection for CNC.
    # Use a limit order priced 1% below LTP to guarantee immediate fill.
    ltp_data = kite.ltp([f"NSE:{trade.symbol}"])
    ltp = ltp_data[f"NSE:{trade.symbol}"]["last_price"]
    limit_price = round(ltp - 0.5, 1)

    order_id = kite.place_order(
        variety="regular",
        exchange="NSE",
        tradingsymbol=trade.symbol,
        transaction_type="SELL",
        quantity=trade.qty,
        order_type="LIMIT",
        price=limit_price,
        product="CNC",
        validity="DAY",
    )
    log_order(db, trade.id, "MARKET_SELL", "placed", kite_order_id=str(order_id))

    from app.kite.orders import wait_for_fill
    filled = wait_for_fill(kite, str(order_id), timeout_seconds=120)
    if filled:
        from datetime import date
        trade.status = "CLOSED"
        trade.exit_date = datetime.utcnow()
        trade.exit_price = filled["average_price"]
        trade.exit_reason = "manual"
        trade.pnl_inr = (trade.exit_price - trade.entry_price) * trade.qty
        trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
        trade.days_held = (trade.exit_date.date() - trade.entry_date.date()).days
        db.commit()
        logger.info(f"Force exit complete for trade {trade.id} @ {trade.exit_price}")
