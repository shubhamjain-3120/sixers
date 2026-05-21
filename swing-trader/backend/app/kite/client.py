import time
import threading
import logging
from typing import Optional
from kiteconnect import KiteConnect
from sqlalchemy.orm import Session
from app.config import settings
from app.kite.auth import get_valid_token

logger = logging.getLogger(__name__)

# Token bucket: 3 req/sec general, 1 req/sec historical
_lock = threading.Lock()
_last_call_time = 0.0
_GENERAL_INTERVAL = 0.34   # ~3/sec
_HISTORICAL_INTERVAL = 0.35  # 1/sec (enforced by caller passing sleep=True)


def _throttle(interval: float = _GENERAL_INTERVAL):
    global _last_call_time
    with _lock:
        now = time.monotonic()
        wait = interval - (now - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.monotonic()


class RateLimitedKite:
    """Thin wrapper around KiteConnect that enforces rate limits."""

    def __init__(self, kite: KiteConnect):
        self._kite = kite

    def ltp(self, instruments):
        _throttle()
        return self._kite.ltp(instruments)

    def quote(self, instruments):
        _throttle()
        return self._kite.quote(instruments)

    def historical_data(self, instrument_token, from_date, to_date, interval, continuous=False, oi=False):
        _throttle(_HISTORICAL_INTERVAL)
        return self._kite.historical_data(instrument_token, from_date, to_date, interval, continuous, oi)

    def instruments(self, exchange=None):
        _throttle()
        return self._kite.instruments(exchange)

    def orders(self):
        _throttle()
        return self._kite.orders()

    def place_order(self, **kwargs):
        _throttle(0.12)  # 10/sec
        return self._kite.place_order(**kwargs)

    def cancel_order(self, variety, order_id):
        _throttle(0.12)
        return self._kite.cancel_order(variety=variety, order_id=order_id)

    def place_gtt(self, **kwargs):
        _throttle()
        return self._kite.place_gtt(**kwargs)

    def modify_gtt(self, trigger_id, trigger_type, tradingsymbol, exchange,
                   trigger_values, last_price, orders):
        _throttle()
        return self._kite.modify_gtt(
            trigger_id, trigger_type, tradingsymbol, exchange,
            trigger_values, last_price, orders,
        )

    def delete_gtt(self, trigger_id):
        _throttle()
        return self._kite.delete_gtt(trigger_id)

    def get_gtts(self):
        _throttle()
        return self._kite.get_gtts()


def get_kite_client(db: Session) -> Optional[RateLimitedKite]:
    token = get_valid_token(db)
    if not token:
        logger.warning("No valid Kite token; skipping job")
        return None
    kite = KiteConnect(api_key=settings.kite_api_key)
    kite.set_access_token(token.access_token)
    return RateLimitedKite(kite)
