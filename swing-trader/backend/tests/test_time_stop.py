"""Tests for M-10: time-stop job (day-15 force exit logic)."""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, call

from app.db.models import Config, Trade, OrderLog
from app.trading.time_stop import run_time_stop, count_trading_days


@pytest.fixture
def cfg(db):
    c = Config(
        id=1,
        total_capital_inr=100_000,
        nifty50_alloc_pct=15.0,
        target_pct=2.0,
        stop_loss_pct=4.0,
        time_stop_days=15,
        max_concurrent_positions=8,
        min_score_threshold=60.0,
    )
    db.add(c)
    db.commit()
    return c


def _open_trade(db, symbol="SBIN", entry_days_ago=16, gtt_id=1001, qty=10, entry_price=500.0):
    entry_dt = datetime.utcnow() - timedelta(days=entry_days_ago)
    t = Trade(
        symbol=symbol,
        segment="NIFTY50_STOCK",
        entry_date=entry_dt,
        entry_price=entry_price,
        qty=qty,
        capital_deployed=entry_price * qty,
        initial_target_price=round(entry_price * 1.02, 1),
        initial_sl_price=round(entry_price * 0.96, 1),
        active_gtt_id=gtt_id,
        gtt_tag=f"trade_test_{gtt_id}",
        status="OPEN",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _filled_order(fill_price: float, symbol: str = "SBIN", qty: int = 10) -> dict:
    return {
        "order_id": "ORD999",
        "tradingsymbol": symbol,
        "transaction_type": "SELL",
        "status": "COMPLETE",
        "quantity": qty,
        "average_price": fill_price,
        "order_timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _mock_kite(fill_price: float = 495.0) -> MagicMock:
    kite = MagicMock()
    kite.place_order.return_value = "ORD999"
    kite.orders.return_value = [_filled_order(fill_price)]
    return kite


@pytest.fixture(autouse=True)
def patch_wait_for_fill(monkeypatch):
    """Replace wait_for_fill with an instant version that returns the first COMPLETE order."""
    def _instant_fill(kite, order_id, timeout_seconds=300):
        for o in kite.orders():
            if o.get("order_id") == order_id and o.get("status") == "COMPLETE":
                return o
        return None
    monkeypatch.setattr("app.trading.time_stop.wait_for_fill", _instant_fill)


# ── count_trading_days ────────────────────────────────────────────────────────

def test_count_trading_days_excludes_weekends():
    # Mon → next Mon (7 calendar days) = 5 trading days
    monday = date(2026, 5, 18)
    next_monday = date(2026, 5, 25)
    assert count_trading_days(monday, next_monday) == 5


def test_count_trading_days_same_day_is_zero():
    d = date(2026, 5, 20)
    assert count_trading_days(d, d) == 0


def test_count_trading_days_across_weekend():
    # Fri to Mon = 1 trading day (Monday only)
    friday = date(2026, 5, 22)
    monday = date(2026, 5, 25)
    assert count_trading_days(friday, monday) == 1


# ── No positions ──────────────────────────────────────────────────────────────

def test_time_stop_no_positions(db, cfg):
    kite = MagicMock()
    run_time_stop(db, kite)
    kite.place_order.assert_not_called()
    kite.delete_gtt.assert_not_called()


# ── Position below threshold → not stopped ───────────────────────────────────

def test_time_stop_skips_young_position(db, cfg):
    """A position held for only 5 trading days must not be exited."""
    _open_trade(db, entry_days_ago=5)
    kite = MagicMock()
    run_time_stop(db, kite)
    kite.place_order.assert_not_called()


# ── Position at threshold → fired ────────────────────────────────────────────

def test_time_stop_fires_at_threshold(db, cfg):
    """Position held >= 15 trading days gets a market sell."""
    trade = _open_trade(db, entry_days_ago=22, gtt_id=1001)  # ~22 cal days ≈ 15-16 trading days
    kite = _mock_kite(fill_price=490.0)

    run_time_stop(db, kite)

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "time_stop"
    assert trade.exit_price == 490.0
    assert trade.pnl_inr == (490.0 - 500.0) * 10
    assert abs(trade.pnl_pct - (-2.0)) < 0.01


def test_time_stop_cancels_gtt_before_sell(db, cfg):
    """GTT is cancelled before the market sell is placed."""
    _open_trade(db, entry_days_ago=22, gtt_id=1001)
    kite = _mock_kite()
    call_order = []
    kite.delete_gtt.side_effect = lambda *a, **kw: call_order.append("cancel_gtt")
    original_place = kite.place_order.return_value
    kite.place_order.side_effect = lambda *a, **kw: call_order.append("place_order") or original_place

    run_time_stop(db, kite)

    assert call_order[0] == "cancel_gtt"
    assert call_order[1] == "place_order"


def test_time_stop_market_sell_is_cncmarket(db, cfg):
    """Market sell order must be CNC + MARKET type."""
    _open_trade(db, entry_days_ago=22)
    kite = _mock_kite()

    run_time_stop(db, kite)

    call_kwargs = kite.place_order.call_args.kwargs
    assert call_kwargs["order_type"] == "MARKET"
    assert call_kwargs["product"] == "CNC"
    assert call_kwargs["transaction_type"] == "SELL"


def test_time_stop_logs_order(db, cfg):
    """TIME_STOP_FIRED action is written to order_log."""
    trade = _open_trade(db, entry_days_ago=22)
    kite = _mock_kite(fill_price=505.0)

    run_time_stop(db, kite)

    logs = db.query(OrderLog).filter(OrderLog.trade_id == trade.id).all()
    actions = {l.action for l in logs}
    assert "TIME_STOP_FIRED" in actions


# ── GTT cancel failure doesn't abort the sell ────────────────────────────────

def test_time_stop_gtt_cancel_failure_continues(db, cfg):
    """Even if GTT cancel throws, the market sell is still placed."""
    trade = _open_trade(db, entry_days_ago=22, gtt_id=1001)
    kite = _mock_kite(fill_price=495.0)
    kite.delete_gtt.side_effect = Exception("gtt not found")

    run_time_stop(db, kite)

    db.refresh(trade)
    # Market sell still happened despite GTT cancel failure
    kite.place_order.assert_called_once()
    assert trade.status == "CLOSED"


# ── Multiple positions, only old ones stopped ────────────────────────────────

def test_time_stop_only_old_positions_exited(db, cfg):
    """Only positions exceeding the day threshold are exited."""
    old = _open_trade(db, symbol="SBIN", entry_days_ago=22, gtt_id=1001)
    young = _open_trade(db, symbol="HDFCBANK", entry_days_ago=5, gtt_id=1002)

    kite = MagicMock()
    kite.place_order.return_value = "ORD999"
    kite.orders.return_value = [_filled_order(490.0, symbol="SBIN")]

    run_time_stop(db, kite)

    db.refresh(old)
    db.refresh(young)
    assert old.status == "CLOSED"
    assert young.status == "OPEN"
    assert kite.place_order.call_count == 1


# ── No fill within timeout → trade stays OPEN ───────────────────────────────

def test_time_stop_no_fill_leaves_trade_open(db, cfg, monkeypatch):
    """If wait_for_fill returns None (timeout), trade remains OPEN."""
    trade = _open_trade(db, entry_days_ago=22, gtt_id=1001)
    kite = MagicMock()
    kite.place_order.return_value = "ORD999"
    monkeypatch.setattr("app.trading.time_stop.wait_for_fill", lambda *a, **kw: None)

    run_time_stop(db, kite)

    db.refresh(trade)
    assert trade.status == "OPEN"
