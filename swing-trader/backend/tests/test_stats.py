"""Tests for M-12: stats summary and equity curve endpoints."""
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient

from app.db.models import Config, Trade, OhlcvDaily
from app.db.session import get_db
from app.main import app
from tests._db import TestingSessionLocal, override_get_db


client = TestClient(app)


@pytest.fixture(autouse=True)
def _install_override_and_seed(_create_drop_tables):
    # Install the get_db override fresh for each test, remove after to prevent
    # leaking into other test modules that also override get_db.
    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    session.add(Config(id=1, total_capital_inr=500000))
    session.commit()
    session.close()
    yield
    app.dependency_overrides.pop(get_db, None)


def _make_trade(db, symbol: str, pnl_pct: float, exit_reason: str,
                llm_verdict: str = "NOISE", badge: str = "GREEN",
                exit_date: date = None) -> Trade:
    entry = datetime(2026, 4, 1, 10, 0)
    ed = datetime.combine(exit_date or date(2026, 4, 10), datetime.min.time())
    entry_price = 1000.0
    exit_price = entry_price * (1 + pnl_pct / 100)
    t = Trade(
        symbol=symbol,
        segment="NIFTY50_STOCK",
        entry_date=entry,
        entry_price=entry_price,
        qty=10,
        capital_deployed=10000.0,
        initial_target_price=entry_price * 1.02,
        initial_sl_price=entry_price * 0.96,
        status="CLOSED",
        exit_date=ed,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl_inr=(exit_price - entry_price) * 10,
        pnl_pct=pnl_pct,
        days_held=9,
        badge_at_entry=badge,
        llm_verdict_at_entry=llm_verdict,
        trailing_state="initial",
        gtt_tag=f"trade_{symbol.lower()}",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ── /api/stats/summary ────────────────────────────────────────────────────────

class TestStatsSummary:
    def test_empty_db_returns_zeros(self):
        r = client.get("/api/stats/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_closed_trades"] == 0
        assert data["win_rate"] == 0.0
        assert data["open_positions"] == 0

    def test_three_closed_trades_win_rate(self, db):
        # Acceptance test scenario: 3 closed trades
        _make_trade(db, "HDFCBANK", pnl_pct=2.1, exit_reason="target")
        _make_trade(db, "RELIANCE", pnl_pct=1.5, exit_reason="trailing_stop")
        _make_trade(db, "TCS", pnl_pct=-3.8, exit_reason="stop_loss")

        r = client.get("/api/stats/summary")
        assert r.status_code == 200
        data = r.json()

        assert data["total_closed_trades"] == 3
        assert abs(data["win_rate"] - 2 / 3) < 0.01
        assert data["avg_win_pct"] > 0
        assert data["avg_loss_pct"] < 0

    def test_exit_reason_breakdown(self, db):
        _make_trade(db, "HDFCBANK", pnl_pct=2.1, exit_reason="target")
        _make_trade(db, "RELIANCE", pnl_pct=1.5, exit_reason="trailing_stop")
        _make_trade(db, "TCS", pnl_pct=-3.8, exit_reason="stop_loss")

        r = client.get("/api/stats/summary")
        data = r.json()
        by_reason = data["by_exit_reason"]

        assert by_reason["target"] == 1
        assert by_reason["trailing_stop"] == 1
        assert by_reason["stop_loss"] == 1
        assert by_reason["time_stop"] == 0
        assert by_reason["manual"] == 0

    def test_by_llm_verdict_breakdown(self, db):
        _make_trade(db, "HDFCBANK", pnl_pct=2.1, exit_reason="target", llm_verdict="NOISE")
        _make_trade(db, "RELIANCE", pnl_pct=-1.5, exit_reason="stop_loss", llm_verdict="NOISE")
        _make_trade(db, "TCS", pnl_pct=2.0, exit_reason="target", llm_verdict="MIXED")

        r = client.get("/api/stats/summary")
        data = r.json()
        by_verdict = data["by_llm_verdict"]

        assert "NOISE" in by_verdict
        assert by_verdict["NOISE"]["trades"] == 2
        assert abs(by_verdict["NOISE"]["win_rate"] - 0.5) < 0.01
        assert "MIXED" in by_verdict
        assert by_verdict["MIXED"]["trades"] == 1
        assert by_verdict["MIXED"]["win_rate"] == 1.0

    def test_capital_accounting(self, db):
        # One open trade deploys 15000
        open_trade = Trade(
            symbol="SBIN", segment="NIFTY50_STOCK",
            entry_date=datetime(2026, 4, 1, 10, 0),
            entry_price=500.0, qty=30,
            capital_deployed=15000.0,
            initial_target_price=510.0,
            initial_sl_price=480.0,
            status="OPEN",
            trailing_state="initial",
            gtt_tag="trade_sbin",
        )
        db.add(open_trade)
        db.commit()

        r = client.get("/api/stats/summary")
        data = r.json()
        assert data["open_positions"] == 1
        assert data["capital_deployed"] == 15000.0
        assert data["capital_available"] == 500000 - 15000

    def test_expectancy_formula(self, db):
        # 2 wins (+2%), 1 loss (-4%)
        _make_trade(db, "A", pnl_pct=2.0, exit_reason="target")
        _make_trade(db, "B", pnl_pct=2.0, exit_reason="target")
        _make_trade(db, "C", pnl_pct=-4.0, exit_reason="stop_loss")

        r = client.get("/api/stats/summary")
        data = r.json()
        # win_rate=2/3, avg_win=2.0, avg_loss=-4.0
        # expectancy = (2/3)*2 + (1/3)*(-4) = 4/3 - 4/3 = 0
        assert abs(data["expectancy_pct"]) < 0.1


# ── /api/stats/equity-curve ───────────────────────────────────────────────────

class TestEquityCurve:
    def test_empty_returns_empty_list(self):
        r = client.get("/api/stats/equity-curve?days=90")
        assert r.status_code == 200
        assert r.json() == []

    def test_cumulative_pnl_ordering(self, db):
        _make_trade(db, "A", pnl_pct=2.0, exit_reason="target", exit_date=date(2026, 4, 5))
        _make_trade(db, "B", pnl_pct=-1.0, exit_reason="stop_loss", exit_date=date(2026, 4, 8))
        _make_trade(db, "C", pnl_pct=3.0, exit_reason="target", exit_date=date(2026, 4, 10))

        r = client.get("/api/stats/equity-curve?days=90")
        assert r.status_code == 200
        points = r.json()

        assert len(points) == 3
        # Must be sorted by date ascending
        dates = [p["date"] for p in points]
        assert dates == sorted(dates)
        # Cumulative: each equity_inr >= previous
        pnl_A = 2.0 / 100 * 10000  # 10 qty * entry 1000 = 200
        pnl_B = -1.0 / 100 * 10000  # -100
        pnl_C = 3.0 / 100 * 10000  # 300

        assert abs(points[0]["equity_inr"] - pnl_A) < 1
        assert abs(points[1]["equity_inr"] - (pnl_A + pnl_B)) < 1
        assert abs(points[2]["equity_inr"] - (pnl_A + pnl_B + pnl_C)) < 1

    def test_days_filter_excludes_old_trades(self, db):
        _make_trade(db, "OLD", pnl_pct=5.0, exit_reason="target",
                    exit_date=date.today() - timedelta(days=100))
        _make_trade(db, "NEW", pnl_pct=2.0, exit_reason="target",
                    exit_date=date.today() - timedelta(days=5))

        r = client.get("/api/stats/equity-curve?days=90")
        points = r.json()
        symbols_in_range = [p for p in points]
        assert len(symbols_in_range) == 1


# ── /api/trades/{trade_id} ───────────────────────────────────────────────────

class TestTradeDetail:
    def test_returns_404_for_missing(self):
        r = client.get("/api/trades/9999")
        assert r.status_code == 404

    def test_returns_trade_fields(self, db):
        t = _make_trade(db, "HDFCBANK", pnl_pct=2.0, exit_reason="target")
        r = client.get(f"/api/trades/{t.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "HDFCBANK"
        assert data["exit_reason"] == "target"
        assert abs(data["pnl_pct"] - 2.0) < 0.01

    def test_includes_ohlcv_when_available(self, db):
        t = _make_trade(db, "HDFCBANK", pnl_pct=2.0, exit_reason="target",
                        exit_date=date(2026, 4, 10))
        # Insert some OHLCV rows
        for i in range(5):
            db.add(OhlcvDaily(
                symbol="HDFCBANK",
                date=date(2026, 4, 1) + timedelta(days=i),
                open=1000.0, high=1010.0, low=995.0, close=1005.0, volume=1000000,
            ))
        db.commit()

        r = client.get(f"/api/trades/{t.id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["ohlcv"]) == 5

    def test_ohlcv_empty_when_no_data(self, db):
        t = _make_trade(db, "RELIANCE", pnl_pct=-3.0, exit_reason="stop_loss")
        r = client.get(f"/api/trades/{t.id}")
        assert r.status_code == 200
        assert r.json()["ohlcv"] == []
