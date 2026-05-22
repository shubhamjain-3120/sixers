"""Tests for M-8: position management cycle (trailing stop logic and exit reconciliation)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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
        trail_distance_pct=1.0,
        trail_lock_floor_pct=0.5,
        max_concurrent_positions=8,
        min_score_threshold=60.0,
    )
    db.add(c)
    db.commit()
    return c


def _open_trade(db, symbol="SBIN", entry_price=500.0, qty=10, gtt_id=1001,
                gtt_tag="trade_abc123", state="initial", current_sl=None, hwm=None):
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
        trailing_state=state,
        high_water_mark=hwm or entry_price,
        current_sl_price=current_sl or round(entry_price * 0.96, 1),
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
    # Returns early, no crash
    assert report.positions == 1


# ── High water mark updated ───────────────────────────────────────────────────

def test_cycle_updates_high_water_mark(db, cfg):
    trade = _open_trade(db, entry_price=500.0, hwm=500.0)
    active_gtt = {"id": 1001, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}
    kite = _mock_kite({"SBIN": 510.0}, [active_gtt])

    run_cycle(db, kite)

    db.refresh(trade)
    assert trade.high_water_mark == 510.0  # updated to new LTP


def test_cycle_hwm_never_decreases(db, cfg):
    trade = _open_trade(db, entry_price=500.0, hwm=520.0)
    active_gtt = {"id": 1001, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}
    kite = _mock_kite({"SBIN": 510.0}, [active_gtt])  # LTP < HWM

    run_cycle(db, kite)

    db.refresh(trade)
    assert trade.high_water_mark == 520.0  # unchanged


# ── Initial → Trailing transition ─────────────────────────────────────────────

def test_cycle_trail_engaged_at_target(db, cfg):
    """When LTP crosses entry * 1.02, OCO GTT replaced by single trailing GTT."""
    entry = 500.0
    trade = _open_trade(db, entry_price=entry, gtt_id=1001)
    active_gtt = {"id": 1001, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}
    ltp = entry * 1.025  # above +2% target trigger

    kite = _mock_kite({"SBIN": ltp}, [active_gtt])
    kite.delete_gtt.return_value = None
    kite.place_gtt.return_value = {"trigger_id": 2002}

    report = run_cycle(db, kite)

    db.refresh(trade)
    assert trade.trailing_state == "trailing"
    assert trade.active_gtt_id == 2002
    kite.delete_gtt.assert_called_once_with(1001)

    # Verify trailing GTT was placed as single-leg
    call_kwargs = kite.place_gtt.call_args.kwargs
    assert call_kwargs["trigger_type"] == "single"
    assert len(call_kwargs["trigger_values"]) == 1
    assert call_kwargs["meta"] == {"tag": "trade_abc123"}

    report_sl = trade.current_sl_price
    lock_floor = entry * 1.005
    hw_based = ltp * 0.99
    assert abs(report_sl - max(lock_floor, hw_based)) < 0.05

    assert report.trails_engaged == 1


def test_cycle_no_trail_below_target(db, cfg):
    """LTP below +2% → stay in initial state, no GTT replacement."""
    entry = 500.0
    trade = _open_trade(db, entry_price=entry, gtt_id=1001)
    active_gtt = {"id": 1001, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}
    ltp = entry * 1.01  # only +1%, below 2% threshold

    kite = _mock_kite({"SBIN": ltp}, [active_gtt])

    report = run_cycle(db, kite)

    db.refresh(trade)
    assert trade.trailing_state == "initial"
    kite.delete_gtt.assert_not_called()
    kite.place_gtt.assert_not_called()
    assert report.trails_engaged == 0


def test_cycle_trail_sl_lock_floor_respected(db, cfg):
    """Lock floor (entry * 1.005) enforced when HWM-based SL would be below it."""
    entry = 500.0
    # LTP just barely above target — HWM-based SL would be below lock_floor
    ltp = entry * 1.021
    trade = _open_trade(db, entry_price=entry, gtt_id=1001, hwm=ltp)
    active_gtt = {"id": 1001, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}

    kite = _mock_kite({"SBIN": ltp}, [active_gtt])
    kite.place_gtt.return_value = {"trigger_id": 2002}

    run_cycle(db, kite)

    db.refresh(trade)
    lock_floor = entry * 1.005
    assert trade.current_sl_price >= lock_floor - 0.01


# ── Trailing SL trail-up ──────────────────────────────────────────────────────

def test_cycle_trailing_sl_updates_on_new_hwm(db, cfg):
    """In trailing state, when HWM moves up, SL is modified via modify_gtt."""
    entry = 500.0
    old_hwm = 510.0
    old_sl = old_hwm * 0.99  # 504.9

    trade = _open_trade(db, entry_price=entry, gtt_id=2002,
                        gtt_tag="trade_abc123", state="trailing",
                        current_sl=old_sl, hwm=old_hwm)
    new_ltp = 520.0  # new HWM
    active_gtt = {"id": 2002, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}

    kite = _mock_kite({"SBIN": new_ltp}, [active_gtt])

    report = run_cycle(db, kite)

    db.refresh(trade)
    assert trade.high_water_mark == new_ltp
    expected_sl = new_ltp * 0.99  # 514.8
    assert abs(trade.current_sl_price - expected_sl) < 0.1

    kite.modify_gtt.assert_called_once()
    modify_kwargs = kite.modify_gtt.call_args.kwargs
    assert modify_kwargs["trigger_id"] == 2002
    assert len(modify_kwargs["trigger_values"]) == 1

    assert report.trails_updated == 1


def test_cycle_trailing_no_modify_below_min_move(db, cfg):
    """SL update skipped when candidate is < 5 paise above current SL."""
    entry = 500.0
    old_sl = 514.80
    old_hwm = 520.0

    trade = _open_trade(db, entry_price=entry, gtt_id=2002,
                        gtt_tag="trade_abc123", state="trailing",
                        current_sl=old_sl, hwm=old_hwm)
    # LTP barely above old HWM — candidate SL delta < 0.05
    new_ltp = 520.01
    active_gtt = {"id": 2002, "status": "active", "meta": {"tag": "trade_abc123"}, "updated_at": None}

    kite = _mock_kite({"SBIN": new_ltp}, [active_gtt])

    run_cycle(db, kite)

    kite.modify_gtt.assert_not_called()


# ── GTT lookup: tag-based primary, ID fallback ───────────────────────────────

def test_cycle_gtt_lookup_by_tag_takes_precedence(db, cfg):
    """Tag-based lookup used even when active_gtt_id points to a different id."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=9999, gtt_tag="trade_tagtest")
    # GTT returned by Kite has a different numeric id but correct tag
    tagged_gtt = {"id": 1234, "status": "active", "meta": {"tag": "trade_tagtest"}, "updated_at": None}
    ltp = 500.0 * 1.025
    kite = _mock_kite({"SBIN": ltp}, [tagged_gtt])
    kite.place_gtt.return_value = {"trigger_id": 5555}

    run_cycle(db, kite)

    db.refresh(trade)
    # Trail was engaged — delete_gtt called with the ID from the tagged GTT, not active_gtt_id
    kite.delete_gtt.assert_called_once_with(1234)


def test_cycle_gtt_fallback_to_id(db, cfg):
    """When GTT has no meta tag, falls back to ID-based lookup."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001, gtt_tag="trade_abc123")
    # GTT has no meta tag (legacy)
    untagged_gtt = {"id": 1001, "status": "active", "meta": None, "updated_at": None}
    ltp = 500.0  # below target, no trail
    kite = _mock_kite({"SBIN": ltp}, [untagged_gtt])

    run_cycle(db, kite)
    # No crash — ID fallback works, LTP below target so no action taken
    kite.modify_gtt.assert_not_called()


# ── Exit reconciliation ───────────────────────────────────────────────────────

def test_cycle_reconciles_triggered_gtt(db, cfg):
    """When GTT status is 'triggered', the cycle calls reconcile_exit and marks trade CLOSED."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001, state="initial")
    triggered_gtt = {
        "id": 1001,
        "status": "triggered",
        "meta": {"tag": "trade_abc123"},
        "updated_at": "2026-05-21 10:30:00",
    }
    fill_order = {
        "order_id": "SELL001",
        "tradingsymbol": "SBIN",
        "transaction_type": "SELL",
        "status": "COMPLETE",
        "quantity": 10,
        "average_price": 520.0,
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


def test_cycle_reconciles_trailing_stop_exit(db, cfg):
    """Trailing state exit sets exit_reason='trailing_stop'."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=2002,
                        gtt_tag="trade_trail99", state="trailing",
                        current_sl=510.0, hwm=520.0)
    triggered_gtt = {
        "id": 2002,
        "status": "triggered",
        "meta": {"tag": "trade_trail99"},
        "updated_at": "2026-05-21 11:00:00",
    }
    fill_order = {
        "order_id": "SELL002",
        "tradingsymbol": "SBIN",
        "transaction_type": "SELL",
        "status": "COMPLETE",
        "quantity": 10,
        "average_price": 509.0,
        "order_timestamp": "2026-05-21 11:00:03",
    }
    kite = _mock_kite({"SBIN": 509.0}, [triggered_gtt])
    kite.orders.return_value = [fill_order]

    run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "CLOSED"
    assert trade.exit_reason == "trailing_stop"
    assert trade.pnl_inr == (509.0 - 500.0) * 10


def test_cycle_reconcile_no_matching_order_logs_warning(db, cfg, caplog):
    """If no sell order matches the triggered GTT, trade stays OPEN with a warning."""
    import logging
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001)
    triggered_gtt = {
        "id": 1001,
        "status": "triggered",
        "meta": {"tag": "trade_abc123"},
        "updated_at": "2026-05-21 10:30:00",
    }
    kite = _mock_kite({"SBIN": 490.0}, [triggered_gtt])
    kite.orders.return_value = []  # no matching fill

    with caplog.at_level(logging.WARNING):
        run_cycle(db, kite)

    db.refresh(trade)
    assert trade.status == "OPEN"
    assert "Could not reconcile" in caplog.text


# ── Multiple positions in one cycle ──────────────────────────────────────────

def test_cycle_handles_multiple_positions(db, cfg):
    """All open positions processed in a single LTP batch call."""
    t1 = _open_trade(db, symbol="SBIN", entry_price=500.0, qty=10,
                     gtt_id=1001, gtt_tag="trade_001")
    t2 = _open_trade(db, symbol="HDFCBANK", entry_price=1500.0, qty=3,
                     gtt_id=1002, gtt_tag="trade_002")

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
    # Single LTP batch call covering both symbols
    assert kite.ltp.call_count == 1
    keys_called = set(kite.ltp.call_args[0][0])
    assert "NSE:SBIN" in keys_called
    assert "NSE:HDFCBANK" in keys_called


# ── reconcile_exit unit tests (direct) ───────────────────────────────────────

def test_reconcile_exit_stop_loss_reason(db, cfg):
    """Exit below initial target classified as stop_loss."""
    trade = _open_trade(db, entry_price=500.0, gtt_id=1001, state="initial")
    trade.initial_target_price = 510.0
    db.commit()

    gtt = {"id": 1001, "status": "triggered", "meta": {}, "updated_at": "2026-05-21 09:45:00"}
    fill_order = {
        "order_id": "SELL_SL",
        "tradingsymbol": "SBIN",
        "transaction_type": "SELL",
        "status": "COMPLETE",
        "quantity": 10,
        "average_price": 480.0,
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
    mock_kite.orders.return_value = []  # nothing matches

    reconcile_exit(db, mock_kite, trade, gtt)

    db.refresh(trade)
    assert trade.status == "OPEN"


def test_reconcile_exit_outside_time_window_ignored(db, cfg):
    """Sell order more than 120s from GTT trigger timestamp is not matched."""
    trade = _open_trade(db)
    gtt = {"id": 1001, "status": "triggered", "meta": {}, "updated_at": "2026-05-21 09:45:00"}
    far_order = {
        "order_id": "SELL_FAR",
        "tradingsymbol": "SBIN",
        "transaction_type": "SELL",
        "status": "COMPLETE",
        "quantity": 10,
        "average_price": 490.0,
        "order_timestamp": "2026-05-21 09:50:00",  # 5 min later — outside ±120s
    }
    mock_kite = MagicMock()
    mock_kite.orders.return_value = [far_order]

    reconcile_exit(db, mock_kite, trade, gtt)

    db.refresh(trade)
    assert trade.status == "OPEN"
