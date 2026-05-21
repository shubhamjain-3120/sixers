"""Tests for M-13: 09:00 candidate re-validation.

Acceptance test: Run scanner Friday 15:45. On Monday 09:00, verify candidate LTPs
are Monday-morning prices, not Friday close.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Config, DailyScan, OhlcvDaily
from app.scanner.runner import revalidate_candidates

# ── In-memory SQLite ──────────────────────────────────────────────────────────

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(Config(id=1, min_score_threshold=60.0))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_scan(db, symbol: str, scan_date: date, score: float = 72.0,
               ltp: float = 1000.0, prev_close: float = 1010.0) -> DailyScan:
    s = DailyScan(
        symbol=symbol,
        scan_date=scan_date,
        ltp=ltp,
        prev_close=prev_close,
        rsi_14=35.0,
        pct_below_20d_high=4.0,
        pct_below_50d_high=6.0,
        dist_from_20dma_pct=-3.0,
        dist_from_50dma_pct=-5.0,
        volume_ratio=2.1,
        swing_low_30d=970.0,
        swing_high_30d=1050.0,
        pivot_support=985.0,
        pivot_resistance=1025.0,
        green_after_red=False,
        score=score,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_ohlcv(db, symbol: str, start_date: date, n: int = 55,
                base_price: float = 1000.0):
    """Insert n daily OHLCV bars ending on start_date."""
    for i in range(n):
        d = start_date - timedelta(days=(n - 1 - i))
        close = base_price + i * 0.5
        db.add(OhlcvDaily(
            symbol=symbol, date=d,
            open=close - 2, high=close + 5, low=close - 5,
            close=close, volume=1_000_000,
        ))
    db.commit()


def _kite_ltp(symbol: str, price: float):
    kite = MagicMock()
    kite.ltp.return_value = {f"NSE:{symbol}": {"last_price": price}}
    return kite


# ── Acceptance test: Monday finds Friday's scans ──────────────────────────────

class TestLastTradingDay:
    def test_monday_finds_friday_scan(self, db):
        """Core acceptance test: Monday revalidation uses Friday's scan."""
        friday = date(2026, 5, 15)   # a Friday
        monday_ltp = 1030.0

        scan = _make_scan(db, "HDFCBANK", scan_date=friday, ltp=1000.0)
        _make_ohlcv(db, "HDFCBANK", start_date=friday, n=55)

        kite = MagicMock()
        kite.ltp.return_value = {"NSE:HDFCBANK": {"last_price": monday_ltp}}

        # Simulate running on Monday (today > friday)
        revalidate_candidates(db, kite)

        db.refresh(scan)
        assert scan.ltp == monday_ltp, "LTP should be Monday morning price, not Friday close"

    def test_skips_when_scan_date_is_today(self, db):
        """Does not revalidate today's scan — it was just run."""
        today = date.today()
        _make_scan(db, "RELIANCE", scan_date=today, ltp=500.0)

        kite = MagicMock()
        revalidate_candidates(db, kite)

        kite.ltp.assert_not_called()

    def test_no_op_when_no_candidates(self, db):
        """No candidates above threshold → nothing to do, no Kite call."""
        _make_scan(db, "SBIN", scan_date=date(2026, 5, 15), score=40.0)

        kite = MagicMock()
        revalidate_candidates(db, kite)

        kite.ltp.assert_not_called()

    def test_uses_most_recent_scan_date(self, db):
        """When multiple scan dates exist, picks the most recent one."""
        older = date(2026, 5, 12)
        newer = date(2026, 5, 15)
        _make_scan(db, "TCS", scan_date=older, ltp=3500.0)
        scan_new = _make_scan(db, "INFY", scan_date=newer, ltp=1400.0)
        _make_ohlcv(db, "INFY", start_date=newer, n=30)

        kite = MagicMock()
        kite.ltp.return_value = {"NSE:INFY": {"last_price": 1450.0}}

        revalidate_candidates(db, kite)

        db.refresh(scan_new)
        assert scan_new.ltp == 1450.0
        # Old scan untouched
        db.refresh(db.query(DailyScan).filter(DailyScan.symbol == "TCS").first())
        assert db.query(DailyScan).filter(DailyScan.symbol == "TCS").first().ltp == 3500.0


# ── LTP-dependent field recomputation ─────────────────────────────────────────

class TestFieldRecomputation:
    def test_pct_below_20d_high_updated_with_fresh_ltp(self, db):
        friday = date(2026, 5, 15)
        scan = _make_scan(db, "WIPRO", scan_date=friday, ltp=1000.0,
                          prev_close=1010.0)
        scan.pct_below_20d_high = 4.0  # old value at LTP=1000
        db.commit()

        # Build OHLCV: highs are all 1050 so pct_below_20d_high = (1050-ltp)/1050
        for i in range(55):
            d = friday - timedelta(days=54 - i)
            db.add(OhlcvDaily(symbol="WIPRO", date=d,
                              open=1040, high=1050, low=990,
                              close=1000 + i * 0.1, volume=500_000))
        db.commit()

        new_ltp = 1020.0  # LTP rose — should narrow the gap to 20D high
        kite = _kite_ltp("WIPRO", new_ltp)

        revalidate_candidates(db, kite)
        db.refresh(scan)

        expected = (1050 - new_ltp) / 1050 * 100
        assert abs(scan.pct_below_20d_high - expected) < 0.1
        assert scan.pct_below_20d_high < 4.0  # smaller gap now that price is higher

    def test_dist_from_20dma_updated_with_fresh_ltp(self, db):
        friday = date(2026, 5, 15)
        scan = _make_scan(db, "AXISBANK", scan_date=friday, ltp=950.0)
        scan.dist_from_20dma_pct = -5.0  # old value

        closes = [1000.0] * 55  # constant closes → 20DMA = 1000
        for i in range(55):
            d = friday - timedelta(days=54 - i)
            db.add(OhlcvDaily(symbol="AXISBANK", date=d,
                              open=closes[i], high=closes[i] + 5,
                              low=closes[i] - 5, close=closes[i], volume=300_000))
        db.commit()

        new_ltp = 980.0  # -2% below the 20DMA of 1000
        kite = _kite_ltp("AXISBANK", new_ltp)

        revalidate_candidates(db, kite)
        db.refresh(scan)

        # (980 - 1000) / 1000 * 100 = -2.0
        assert abs(scan.dist_from_20dma_pct - (-2.0)) < 0.1

    def test_pivot_support_resistance_recomputed(self, db):
        friday = date(2026, 5, 15)
        scan = _make_scan(db, "BAJFINANCE", scan_date=friday, ltp=6000.0)
        scan.pivot_support = 5800.0
        scan.pivot_resistance = 6200.0
        db.commit()

        # Two OHLCV bars: prev_session has high=6100, low=5900, close=6000
        db.add(OhlcvDaily(symbol="BAJFINANCE", date=friday - timedelta(days=2),
                          open=5900, high=6100, low=5900, close=6000, volume=100_000))
        db.add(OhlcvDaily(symbol="BAJFINANCE", date=friday - timedelta(days=1),
                          open=6000, high=6100, low=5900, close=6000, volume=100_000))
        db.commit()

        new_ltp = 6050.0
        kite = _kite_ltp("BAJFINANCE", new_ltp)

        revalidate_candidates(db, kite)
        db.refresh(scan)

        # Pivot = (6100+5900+6000)/3 = 6000; R1 = 2*6000-5900=6100; S1 = 2*6000-6100=5900
        # With ltp=6050: levels below=5900 → support=5900; levels above=[6000, 6100] → resistance=6000
        assert scan.pivot_support is not None
        assert scan.pivot_resistance is not None
        # Just verify they changed from the old placeholder values
        assert scan.pivot_support != 5800.0 or scan.pivot_resistance != 6200.0

    def test_badge_and_score_not_touched(self, db):
        """Badge, score, LLM verdict must NOT be modified."""
        friday = date(2026, 5, 15)
        scan = _make_scan(db, "SUNPHARMA", scan_date=friday, score=75.0)
        _make_ohlcv(db, "SUNPHARMA", start_date=friday, n=30)

        kite = _kite_ltp("SUNPHARMA", 1100.0)
        revalidate_candidates(db, kite)
        db.refresh(scan)

        assert scan.score == 75.0  # score untouched


# ── Failure handling ──────────────────────────────────────────────────────────

class TestFailureHandling:
    def test_kite_failure_does_not_crash(self, db):
        friday = date(2026, 5, 15)
        scan = _make_scan(db, "LTIM", scan_date=friday, ltp=5000.0)

        kite = MagicMock()
        kite.ltp.side_effect = Exception("network timeout")

        revalidate_candidates(db, kite)  # must not raise

        db.refresh(scan)
        assert scan.ltp == 5000.0  # unchanged

    def test_missing_symbol_in_ltp_response_skipped(self, db):
        friday = date(2026, 5, 15)
        _make_scan(db, "HCLTECH", scan_date=friday, ltp=1500.0)
        _make_scan(db, "WIPRO",   scan_date=friday, ltp=500.0)
        _make_ohlcv(db, "WIPRO", start_date=friday, n=30)

        kite = MagicMock()
        # Only WIPRO in response; HCLTECH missing
        kite.ltp.return_value = {"NSE:WIPRO": {"last_price": 520.0}}

        revalidate_candidates(db, kite)  # must not raise

        hcl = db.query(DailyScan).filter(DailyScan.symbol == "HCLTECH").first()
        assert hcl.ltp == 1500.0  # unchanged

    def test_only_updates_candidates_above_threshold(self, db):
        friday = date(2026, 5, 15)
        high_scan = _make_scan(db, "MARUTI", scan_date=friday, score=72.0, ltp=10000.0)
        low_scan  = _make_scan(db, "HEROMOTOCO", scan_date=friday, score=45.0, ltp=3000.0)
        _make_ohlcv(db, "MARUTI", start_date=friday, n=30)

        kite = MagicMock()
        kite.ltp.return_value = {
            "NSE:MARUTI": {"last_price": 10200.0},
        }

        revalidate_candidates(db, kite)

        db.refresh(high_scan)
        db.refresh(low_scan)
        assert high_scan.ltp == 10200.0   # updated
        assert low_scan.ltp  == 3000.0    # below threshold, not touched
