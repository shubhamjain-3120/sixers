"""Tests for position management cycle (exit reconciliation)."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.db.models import Config, Trade, OrderLog
from app.trading.position_cycle import run_cycle, CycleReport
from app.trading.reconcile import reconcile_exit


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


def _open_trade(db, symbol="SBIN", entry_price=500.0, qty=10, gtt_id=1001, gtt_tag="trade_abc123"):
    t = Trade(
        symbol=symbol,
        segment="NIFTY50_STOCK",
        entry_date=datetime.utcnow(),
        entry_price=entry_price,
        qty=qty,
        capital_deployed=entry_price * qty,
        initial_target_price=round(entry_price * 1.02, 1),
        initial_sl_price=round(entry_price * 0.96, 1),
        active_gtt_id=gtt_id,
        gtt_tag=gtt_tag,
        status="OPEN",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _mock_kite(ltp_map: dict, gtts: list) -> MagicMock:
    kite = MagicMock()
    kite.ltp.return_value = {f"NSE:{sym}": {"last_price": price} for sym, price in ltp_map.items()}
    kite.get_gtts.return_value = gtts
    kite.place_gtt.return_value = {"trigger_id": 9999}
    return kite


# ── No-op when no positions ───────────────────────────────────────────────────

def test_cycle_no_positions(db, cfg):
    kite = _mock_kite({}, [])
    report = run_cycle(db, kite)
    assert report.positions == 0
    kite.ltp.assert_not_called()
    kite.get_gtts.assert_not_called()


# ── LTP lookup fails gracefully ───────────────────────────────────────────────

def test_cycle_ltp_fetch_fails(db, cfg):
    _open_trade(db)
    kite = MagicMock()
    kite.ltp.side_effect = Exception("network error")
    kite.get_gtts.return_value = []
    report = run_cycle(db, kite)
    assert report.positions == 1


# ── GTT lookup: tag-based primary, ID fallback ───────────────────────────────

def test_cycle_gtt_lookup_by_tag_takes_precedence(db, cfg):
    """Tag-based lookup finds the GTT even when active_gtt_id points to a different id."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=9999, gtt_tag="trade_tagtest")
    tagged_triggered_gtt = {
        "id": 1234, "status": "triggered",
        "meta": {"tag": "trade_tagtest"}, "updated_at": "2026-05-21 10:30:00",
    }
    fill_order = {
        "order_id": "SELL001", "tradingsymbol": "SBIN",
        "transaction_type": "SELL", "status": "COMPLETE",
        "quantity": 10, "average_price": 520.0,
        "order_timestamp": "2026-05-21 10:30:05",
    }
    kite = _mock_kite({"SBIN": 520.0}, [tagged_triggered_gtt])
    kite.orders.return_value = [fill_order]

    report = run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert report.exits_reconciled == 1


def test_cycle_gtt_fallback_to_id(db, cfg):
    """When GTT has no meta tag, falls back to ID-based lookup."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001, gtt_tag="trade_abc123")
    untagged_gtt = {"id": 1001, "status": "active", "meta": None, "updated_at": None}
    kite = _mock_kite({"SBIN": 500.0}, [untagged_gtt])

    run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "OPEN"


# ── Exit reconciliation ───────────────────────────────────────────────────────

def test_cycle_reconciles_triggered_gtt(db, cfg):
    """When GTT status is 'triggered', the cycle calls reconcile_exit and marks trade CLOSED."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001)
    triggered_gtt = {
        "id": 1001, "status": "triggered",
        "meta": {"tag": "trade_abc123"}, "updated_at": "2026-05-21 10:30:00",
    }
    fill_order = {
        "order_id": "SELL001", "tradingsymbol": "SBIN",
        "transaction_type": "SELL", "status": "COMPLETE",
        "quantity": 10, "average_price": 520.0,
        "order_timestamp": "2026-05-21 10:30:05",
    }
    kite = _mock_kite({"SBIN": 520.0}, [triggered_gtt])
    kite.orders.return_value = [fill_order]

    report = run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert trade.exit_price == 520.0
    assert trade.exit_reason == "target"
    assert trade.pnl_inr == (520.0 - 500.0) * 10
    assert report.exits_reconciled == 1


def test_cycle_reconcile_no_matching_order_logs_warning(db, cfg, caplog):
    """If no sell order matches the triggered GTT, trade stays OPEN with a warning."""
    import logging
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001)
    triggered_gtt = {
        "id": 1001, "status": "triggered",
        "meta": {"tag": "trade_abc123"}, "updated_at": "2026-05-21 10:30:00",
    }
    kite = _mock_kite({"SBIN": 490.0}, [triggered_gtt])
    kite.orders.return_value = []

    with caplog.at_level(logging.WARNING):
        run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "OPEN"
    assert "Could not reconcile" in caplog.text


# ── Multiple positions in one cycle ──────────────────────────────────────────

def test_cycle_handles_multiple_positions(db, cfg):
    """All open positions processed in a single LTP batch call."""
    _open_trade(db, symbol="SBIN", entry_price=500.0, qty=10, gtt_id=1001, gtt_tag="trade_001")
    _open_trade(db, symbol="HDFCBANK", entry_price=1500.0, qty=3, gtt_id=1002, gtt_tag="trade_002")

    gtt1 = {"id": 1001, "status": "active", "meta": {"tag": "trade_001"}, "updated_at": None}
    gtt2 = {"id": 1002, "status": "active", "meta": {"tag": "trade_002"}, "updated_at": None}

    kite = MagicMock()
    kite.ltp.return_value = {
        "NSE:SBIN": {"last_price": 500.0},
        "NSE:HDFCBANK": {"last_price": 1500.0},
    }
    kite.get_gtts.return_value = [gtt1, gtt2]

    report = run_cycle(db, kite)

    assert report.positions == 2
    assert kite.ltp.call_count == 1
    keys_called = set(kite.ltp.call_args[0][0])
    assert "NSE:SBIN" in keys_called
    assert "NSE:HDFCBANK" in keys_called


# ── reconcile_exit unit tests (direct) ───────────────────────────────────────

def test_reconcile_exit_stop_loss_reason(db, cfg):
    """Exit below initial target classified as stop_loss."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001)
    trade.initial_target_price = 510.0
    db.commit()

    gtt = {"id": 1001, "status": "triggered", "meta": {}, "updated_at": "2026-05-21 09:45:00"}
    fill_order = {
        "order_id": "SELL_SL", "tradingsymbol": "SBIN",
        "transaction_type": "SELL", "status": "COMPLETE",
        "quantity": 10, "average_price": 480.0,
        "order_timestamp": "2026-05-21 09:45:02",
    }

    mock_kite = MagicMock()
    mock_kite.orders.return_value = [fill_order]

    reconcile_exit(db, mock_kite, trade, gtt)

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "stop_loss"
    assert trade.pnl_inr == (480.0 - 500.0) * 10
    assert trade.pnl_pct < 0


def test_reconcile_exit_no_matching_sell_order(db, cfg):
    """No matching sell order leaves trade OPEN."""
    trade = _open_trade(db)
    gtt = {"id": 1001, "status": "triggered", "meta": {}, "updated_at": "2026-05-21 09:45:00"}

    mock_kite = MagicMock()
    mock_kite.orders.return_value = []

    reconcile_exit(db, mock_kite, trade, gtt)

    db.refresh(trade)
    assert trade.status == "OPEN"


def test_reconcile_exit_outside_time_window_ignored(db, cfg):
    """Sell order more than 120s from GTT trigger timestamp is not matched."""
    trade = _open_trade(db)
    gtt = {"id": 1001, "status": "triggered", "meta": {}, "updated_at": "2026-05-21 09:45:00"}
    far_order = {
        "order_id": "SELL_FAR", "tradingsymbol": "SBIN",
        "transaction_type": "SELL", "status": "COMPLETE",
        "quantity": 10, "average_price": 490.0,
        "order_timestamp": "2026-05-21 09:50:00",
    }
    mock_kite = MagicMock()
    mock_kite.orders.return_value = [far_order]

    reconcile_exit(db, mock_kite, trade, gtt)

    db.refresh(trade)
    assert trade.status == "OPEN"
