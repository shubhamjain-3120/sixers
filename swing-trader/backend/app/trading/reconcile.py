import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import Trade, OrderLog

logger = logging.getLogger(__name__)


def _parse_dt(val) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    return None


def reconcile_exit(db: Session, kite, trade: Trade, gtt: dict):
    """Match triggered GTT to its resulting sell order and close the trade."""
    gtt_triggered_at = _parse_dt(gtt.get("updated_at")) or datetime.utcnow()

    try:
        orders = kite.orders()
    except Exception as e:
        logger.error(f"Failed to fetch orders during reconciliation: {e}")
        return

    window = timedelta(seconds=120)
    candidates = [
        o for o in orders
        if o.get("tradingsymbol") == trade.symbol
        and o.get("transaction_type") == "SELL"
        and o.get("status") == "COMPLETE"
        and str(o.get("quantity", 0)) == str(trade.qty)
    ]

    def _within_window(o):
        order_ts = _parse_dt(o.get("order_timestamp"))
        return order_ts is not None and abs(order_ts - gtt_triggered_at) <= window

    candidates = [o for o in candidates if _within_window(o)]

    if not candidates:
        logger.warning(f"Could not reconcile exit for {trade.symbol} trade {trade.id}")
        return

    order = candidates[0]
    fill_price = float(order.get("average_price", 0))
    order_time = _parse_dt(order.get("order_timestamp")) or datetime.utcnow()

    trade.status = "CLOSED"
    trade.exit_date = order_time
    trade.exit_price = fill_price
    trade.pnl_inr = (fill_price - trade.entry_price) * trade.qty
    trade.pnl_pct = (fill_price - trade.entry_price) / trade.entry_price * 100
    trade.days_held = (order_time.date() - trade.entry_date.date()).days

    if trade.trailing_state == "trailing":
        trade.exit_reason = "trailing_stop"
    elif trade.initial_target_price and fill_price >= trade.initial_target_price * 0.995:
        trade.exit_reason = "target"
    else:
        trade.exit_reason = "stop_loss"

    db.add(OrderLog(
        trade_id=trade.id,
        kite_order_id=str(order.get("order_id", "")),
        action="EXIT_RECONCILED",
        status="COMPLETE",
        raw_response=str(order),
    ))
    db.commit()
    logger.info(
        f"EXIT_RECONCILED trade={trade.id} {trade.symbol} "
        f"price={fill_price} reason={trade.exit_reason} pnl={trade.pnl_pct:.2f}%"
    )
