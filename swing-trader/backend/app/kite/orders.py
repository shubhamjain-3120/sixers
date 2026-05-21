import time
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import OrderLog

logger = logging.getLogger(__name__)


def log_order(db: Session, trade_id: Optional[int], action: str, status: str,
              kite_order_id: Optional[str] = None, kite_gtt_id: Optional[int] = None,
              raw_response: Optional[str] = None):
    entry = OrderLog(
        trade_id=trade_id,
        kite_order_id=kite_order_id,
        kite_gtt_id=kite_gtt_id,
        action=action,
        status=status,
        raw_response=raw_response,
    )
    db.add(entry)
    db.commit()


def wait_for_fill(kite, order_id: str, timeout_seconds: int = 300) -> Optional[dict]:
    """Poll kite.orders() until order is COMPLETE or timeout.

    Returns order dict on full fill, or the last seen order dict (with partial
    filled_quantity) on timeout so the caller can decide whether to proceed.
    Returns None only if order was CANCELLED/REJECTED with zero fill, or not found.
    """
    deadline = time.monotonic() + timeout_seconds
    last_seen: Optional[dict] = None
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            orders = kite.orders()
            for o in orders:
                if o["order_id"] == order_id:
                    last_seen = o
                    if o["status"] == "COMPLETE":
                        return o
                    if o["status"] in ("CANCELLED", "REJECTED"):
                        filled = o.get("filled_quantity", 0)
                        if filled > 0:
                            logger.warning(f"Order {order_id} {o['status']} with partial fill qty={filled}")
                            return o
                        logger.warning(f"Order {order_id} ended with status {o['status']} and no fill")
                        return None
        except Exception as e:
            logger.error(f"Error polling order {order_id}: {e}")
    logger.warning(f"Order {order_id} not fully filled within {timeout_seconds}s")
    return last_seen  # may have partial fill; caller checks filled_quantity
