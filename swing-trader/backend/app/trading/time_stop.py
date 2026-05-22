import logging
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.db.models import Trade, Config, OrderLog
from app.kite.client import RateLimitedKite
from app.kite.orders import wait_for_fill

logger = logging.getLogger(__name__)


def count_trading_days(start: date, end: date) -> int:
    """Count weekdays (Mon-Fri) between start (exclusive) and end (inclusive)."""
    from datetime import timedelta
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


def run_time_stop(db: Session, kite: RateLimitedKite):
    cfg = db.query(Config).filter(Config.id == 1).first()
    time_stop_days = cfg.time_stop_days if cfg else 15
    today = datetime.utcnow().date()

    positions = db.query(Trade).filter(Trade.status == "OPEN").all()
    for p in positions:
        trading_days_held = count_trading_days(p.entry_date.date(), today)
        if trading_days_held < time_stop_days:
            continue

        logger.info(f"TIME_STOP_FIRED {p.symbol} trade={p.id} days={trading_days_held}")

        if p.active_gtt_id:
            try:
                kite.delete_gtt(p.active_gtt_id)
                db.add(OrderLog(trade_id=p.id, kite_gtt_id=p.active_gtt_id, action="CANCEL_GTT", status="cancelled"))
            except Exception as e:
                logger.warning(f"GTT cancel on time-stop: {e}")

        try:
            order_id = kite.place_order(
                variety="regular",
                exchange="NSE",
                tradingsymbol=p.symbol,
                transaction_type="SELL",
                quantity=p.qty,
                order_type="MARKET",
                product="CNC",
                validity="DAY",
                market_protection=2,
            )
            db.add(OrderLog(trade_id=p.id, kite_order_id=str(order_id), action="MARKET_SELL", status="placed"))
            db.commit()
        except Exception as e:
            logger.error(f"Market sell failed on time-stop for {p.symbol}: {e}")
            continue

        filled = wait_for_fill(kite, str(order_id), timeout_seconds=300)
        if filled:
            exit_price = filled["average_price"]
            exit_time = datetime.utcnow()
            p.status = "CLOSED"
            p.exit_date = exit_time
            p.exit_price = exit_price
            p.exit_reason = "time_stop"
            p.pnl_inr = (exit_price - p.entry_price) * p.qty
            p.pnl_pct = (exit_price - p.entry_price) / p.entry_price * 100
            p.days_held = trading_days_held
            db.add(OrderLog(
                trade_id=p.id, kite_order_id=str(order_id),
                action="TIME_STOP_FIRED", status="complete",
                raw_response=str(filled),
            ))
            db.commit()
            logger.info(f"TIME_STOP_COMPLETE {p.symbol} exit={exit_price} pnl={p.pnl_pct:.2f}%")
        else:
            logger.error(f"Time-stop market sell not filled for {p.symbol} within timeout")
