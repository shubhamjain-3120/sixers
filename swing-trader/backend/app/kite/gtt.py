import logging
from typing import Optional
from app.kite.client import RateLimitedKite
from app.kite.orders import log_order
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def _sl_order_price(sl_price: float) -> float:
    """Price for a LIMIT SL sell order — 2% below trigger to absorb slippage."""
    return round(sl_price * 0.98, 1)


def place_oco_gtt(
    kite: RateLimitedKite,
    db: Session,
    trade_id: int,
    symbol: str,
    qty: int,
    sl_price: float,
    target_price: float,
    ltp: float,
    gtt_tag: str,
) -> int:
    """Place a two-leg OCO GTT. Returns trigger_id."""
    resp = kite.place_gtt(
        trigger_type="two-leg",
        tradingsymbol=symbol,
        exchange="NSE",
        trigger_values=[round(sl_price, 1), round(target_price, 1)],
        last_price=ltp,
        orders=[
            {
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "transaction_type": "SELL",
                "quantity": qty,
                "order_type": "LIMIT",
                "product": "CNC",
                "price": _sl_order_price(sl_price),
            },
            {
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "transaction_type": "SELL",
                "quantity": qty,
                "order_type": "LIMIT",
                "product": "CNC",
                "price": round(target_price, 1),
            },
        ],
        meta={"tag": gtt_tag},
    )
    trigger_id = resp["trigger_id"]
    log_order(db, trade_id, "PLACE_GTT", "placed", kite_gtt_id=trigger_id)
    return trigger_id


def place_single_trail_gtt(
    kite: RateLimitedKite,
    db: Session,
    trade_id: int,
    symbol: str,
    qty: int,
    sl_price: float,
    ltp: float,
    gtt_tag: str,
) -> int:
    """Place a single-leg trailing stop GTT. Returns trigger_id."""
    resp = kite.place_gtt(
        trigger_type="single",
        tradingsymbol=symbol,
        exchange="NSE",
        trigger_values=[round(sl_price, 1)],
        last_price=ltp,
        orders=[
            {
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "transaction_type": "SELL",
                "quantity": qty,
                "order_type": "LIMIT",
                "product": "CNC",
                "price": _sl_order_price(sl_price),
            }
        ],
        meta={"tag": gtt_tag},
    )
    trigger_id = resp["trigger_id"]
    log_order(db, trade_id, "PLACE_GTT", "trail_placed", kite_gtt_id=trigger_id)
    return trigger_id


def modify_trail_gtt(
    kite: RateLimitedKite,
    db: Session,
    trade_id: int,
    trigger_id: int,
    symbol: str,
    qty: int,
    new_sl: float,
    ltp: float,
):
    """Modify an existing single-leg trailing stop GTT to a new SL price."""
    kite.modify_gtt(
        trigger_id=trigger_id,
        trigger_type="single",
        tradingsymbol=symbol,
        exchange="NSE",
        trigger_values=[round(new_sl, 1)],
        last_price=ltp,
        orders=[
            {
                "exchange": "NSE",
                "tradingsymbol": symbol,
                "transaction_type": "SELL",
                "quantity": qty,
                "order_type": "LIMIT",
                "product": "CNC",
                "price": _sl_order_price(new_sl),
            }
        ],
    )
    log_order(db, trade_id, "MODIFY_GTT", "modified", kite_gtt_id=trigger_id)
