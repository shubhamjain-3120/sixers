"""Tests for M-7: order entry, GTT placement, and force exit."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

from app.db.models import Config, Instrument, Trade, KiteToken, SetupClassification, NewsClassification
from app.trading.entry import execute_entry, execute_force_exit
from app.kite.orders import wait_for_fill


@pytest.fixture
def seeded_db(db):
    """DB with a valid Kite token, config, and HDFCBANK instrument."""
    from app.config import settings
    settings.kite_api_key = "test_key"
    settings.kite_api_secret = "test_secret"

    expires = datetime.utcnow() + timedelta(hours=8)
    db.add(KiteToken(access_token="test_token", expires_at=expires))
    db.add(Config(
        id=1,
        total_capital_inr=100_000,
        nifty50_alloc_pct=15.0,
        target_pct=2.0,
        stop_loss_pct=4.0,
        time_stop_days=15,
        max_concurrent_positions=8,
        min_score_threshold=60.0,
    ))
    db.add(Instrument(
        symbol="HDFCBANK",
        name="HDFC Bank",
        segment="NIFTY50_STOCK",
        kite_instrument_token=341249,
        sector="Financial Services",
    ))
    db.commit()
    return db


# ── wait_for_fill tests ───────────────────────────────────────────────────────

def test_wait_for_fill_full_fill():
    mock_kite = MagicMock()
    mock_kite.orders.return_value = [
        {"order_id": "OID1", "status": "COMPLETE", "average_price": 1500.0, "filled_quantity": 10}
    ]
    with patch("time.sleep"):
        result = wait_for_fill(mock_kite, "OID1", timeout_seconds=30)
    assert result is not None
    assert result["status"] == "COMPLETE"
    assert result["filled_quantity"] == 10


def test_wait_for_fill_returns_partial_on_timeout():
    """After timeout, last seen order with partial fill is returned."""
    mock_kite = MagicMock()
    partial = {"order_id": "OID2", "status": "OPEN", "average_price": 1500.0, "filled_quantity": 3}
    mock_kite.orders.return_value = [partial]

    # Sequence: deadline=0+5=5, while(1<5)→enter, while(10<5)→exit
    monotonic_values = iter([0.0, 1.0, 10.0])

    with patch("time.sleep"), patch("app.kite.orders.time.monotonic", side_effect=monotonic_values):
        result = wait_for_fill(mock_kite, "OID2", timeout_seconds=5)

    assert result is not None
    assert result["filled_quantity"] == 3
    assert result["status"] == "OPEN"


def test_wait_for_fill_cancelled_no_fill():
    mock_kite = MagicMock()
    mock_kite.orders.return_value = [
        {"order_id": "OID3", "status": "CANCELLED", "average_price": 0.0, "filled_quantity": 0}
    ]
    with patch("time.sleep"):
        result = wait_for_fill(mock_kite, "OID3", timeout_seconds=30)
    assert result is None


def test_wait_for_fill_cancelled_with_partial():
    """CANCELLED order that partially filled should still be returned."""
    mock_kite = MagicMock()
    mock_kite.orders.return_value = [
        {"order_id": "OID4", "status": "CANCELLED", "average_price": 1480.0, "filled_quantity": 5}
    ]
    with patch("time.sleep"):
        result = wait_for_fill(mock_kite, "OID4", timeout_seconds=30)
    assert result is not None
    assert result["filled_quantity"] == 5


# ── execute_entry tests ───────────────────────────────────────────────────────

def _make_full_fill_order(order_id: str, price: float, qty: int) -> dict:
    return {
        "order_id": order_id,
        "status": "COMPLETE",
        "average_price": price,
        "filled_quantity": qty,
        "transaction_type": "BUY",
        "tradingsymbol": "HDFCBANK",
        "order_timestamp": "2026-05-21 10:15:00",
        "quantity": qty,
    }


def test_execute_entry_full_fill(seeded_db):
    """Full fill → Trade row created, OCO GTT placed, result dict returned."""
    db = seeded_db
    fill_price = 1500.0
    qty = 10  # floor(100_000 * 0.15 / 1500) = floor(10) = 10

    mock_kite = MagicMock()
    mock_kite.ltp.return_value = {"NSE:HDFCBANK": {"last_price": 1500.0}}
    mock_kite.place_order.return_value = "ORDER123"
    mock_kite.orders.return_value = [_make_full_fill_order("ORDER123", fill_price, qty)]
    mock_kite.place_gtt.return_value = {"trigger_id": 9001}

    with patch("app.trading.entry.get_kite_client", return_value=mock_kite), \
         patch("time.sleep"):
        result = execute_entry(db, "HDFCBANK", badge="GREEN", llm_verdict="NOISE")

    assert result is not None
    assert result["fill_price"] == fill_price
    assert result["qty"] == qty
    assert result["gtt_id"] == 9001
    assert abs(result["target_price"] - fill_price * 1.02) < 0.5
    assert abs(result["sl_price"] - fill_price * 0.96) < 0.5

    trade = db.query(Trade).filter(Trade.symbol == "HDFCBANK").first()
    assert trade is not None
    assert trade.status == "OPEN"
    assert trade.badge_at_entry == "GREEN"
    assert trade.llm_verdict_at_entry == "NOISE"
    assert trade.active_gtt_id == 9001

    # Verify OCO GTT was placed with two-leg trigger
    gtt_call = mock_kite.place_gtt.call_args
    assert gtt_call.kwargs["trigger_type"] == "two-leg"
    assert len(gtt_call.kwargs["trigger_values"]) == 2


def test_execute_entry_partial_fill_proceeds(seeded_db):
    """Partial fill at timeout → cancel remainder, proceed with filled qty."""
    db = seeded_db
    fill_price = 1500.0
    full_qty = 10
    partial_qty = 4

    partial_order = {
        "order_id": "ORDER456",
        "status": "OPEN",
        "average_price": fill_price,
        "filled_quantity": partial_qty,
        "transaction_type": "BUY",
        "tradingsymbol": "HDFCBANK",
        "order_timestamp": "2026-05-21 10:15:00",
        "quantity": full_qty,
    }

    mock_kite = MagicMock()
    mock_kite.ltp.return_value = {"NSE:HDFCBANK": {"last_price": fill_price}}
    mock_kite.place_order.return_value = "ORDER456"
    mock_kite.orders.return_value = [partial_order]
    mock_kite.place_gtt.return_value = {"trigger_id": 9002}

    # Force timeout on wait_for_fill so partial_order is returned as last_seen
    import time as time_mod
    call_count = [0]

    def fake_monotonic():
        val = call_count[0] * 100.0
        call_count[0] += 1
        return val

    with patch("app.trading.entry.get_kite_client", return_value=mock_kite), \
         patch("time.sleep"), \
         patch("app.kite.orders.time.monotonic", side_effect=fake_monotonic):
        result = execute_entry(db, "HDFCBANK")

    assert result is not None
    assert result["qty"] == partial_qty
    mock_kite.cancel_order.assert_called_once_with("regular", "ORDER456")

    trade = db.query(Trade).filter(Trade.symbol == "HDFCBANK").first()
    assert trade is not None
    assert trade.qty == partial_qty
    assert trade.status == "OPEN"


def test_execute_entry_no_fill_returns_none(seeded_db):
    """Zero filled qty → cancel order, return None."""
    db = seeded_db

    mock_kite = MagicMock()
    mock_kite.ltp.return_value = {"NSE:HDFCBANK": {"last_price": 1500.0}}
    mock_kite.place_order.return_value = "ORDER789"
    mock_kite.orders.return_value = [
        {"order_id": "ORDER789", "status": "OPEN", "average_price": 0.0, "filled_quantity": 0}
    ]

    import time as time_mod
    call_count = [0]

    def fake_monotonic():
        val = call_count[0] * 100.0
        call_count[0] += 1
        return val

    with patch("app.trading.entry.get_kite_client", return_value=mock_kite), \
         patch("time.sleep"), \
         patch("app.kite.orders.time.monotonic", side_effect=fake_monotonic):
        result = execute_entry(db, "HDFCBANK")

    assert result is None
    mock_kite.cancel_order.assert_called_once()


def test_execute_entry_insufficient_capital(seeded_db):
    """When qty rounds to 0, raises ValueError."""
    db = seeded_db
    mock_kite = MagicMock()
    # LTP so high that floor(15000 / price) == 0
    mock_kite.ltp.return_value = {"NSE:HDFCBANK": {"last_price": 500_000.0}}

    with patch("app.trading.entry.get_kite_client", return_value=mock_kite):
        with pytest.raises(ValueError, match="insufficient_capital"):
            execute_entry(db, "HDFCBANK")


# ── execute_force_exit tests ──────────────────────────────────────────────────

def test_force_exit_cancels_gtt_and_market_sells(seeded_db):
    """Force exit cancels active GTT then places market sell."""
    db = seeded_db
    trade = Trade(
        symbol="HDFCBANK", segment="NIFTY50_STOCK",
        entry_date=datetime.utcnow(), entry_price=1500.0,
        qty=5, capital_deployed=7500.0,
        active_gtt_id=9999, gtt_tag="trade_abc123",
        status="OPEN",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    mock_kite = MagicMock()
    mock_kite.place_order.return_value = "SELL_ORDER_1"
    mock_kite.orders.return_value = [{
        "order_id": "SELL_ORDER_1",
        "status": "COMPLETE",
        "average_price": 1510.0,
        "filled_quantity": 5,
        "transaction_type": "SELL",
        "tradingsymbol": "HDFCBANK",
        "order_timestamp": "2026-05-21 14:00:00",
        "quantity": 5,
    }]

    with patch("app.trading.entry.get_kite_client", return_value=mock_kite), \
         patch("time.sleep"):
        execute_force_exit(db, trade)

    mock_kite.delete_gtt.assert_called_once_with(9999)
    sell_call = mock_kite.place_order.call_args
    assert sell_call.kwargs["transaction_type"] == "SELL"
    assert sell_call.kwargs["order_type"] == "MARKET"

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "manual"
    assert trade.exit_price == 1510.0
    assert abs(trade.pnl_inr - (1510.0 - 1500.0) * 5) < 0.01
