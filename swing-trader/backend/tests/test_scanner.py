"""Tests for signals and scorer (M-4)."""
import pytest
from app.scanner.signals import (
    rsi_14,
    pct_below_high,
    dist_from_sma_pct,
    volume_ratio,
    swing_low_high,
    pivot_s1_r1,
    green_after_red,
    compute_signals,
    SignalsBundle,
)
from app.scanner.scorer import compute_score


# ── RSI ──────────────────────────────────────────────────────────────────────

def test_rsi_all_gains_returns_100():
    closes = [float(i) for i in range(1, 30)]
    assert rsi_14(closes) == 100.0


def test_rsi_all_losses_returns_low():
    closes = [float(i) for i in range(30, 1, -1)]
    # All losses -> avg_gain = 0 -> RSI = 0
    assert rsi_14(closes) == 0.0


def test_rsi_flat_returns_neutral_or_100():
    # No movement -> avg_gain = avg_loss = 0 -> early return 100
    closes = [100.0] * 20
    assert rsi_14(closes) == 100.0


def test_rsi_too_short_returns_default():
    assert rsi_14([1.0, 2.0, 3.0]) == 50.0


def test_rsi_known_values():
    # Classic Wilder example values produce RSI in a reasonable band
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00,
        46.03, 46.41, 46.22, 45.64, 46.21, 46.25, 45.71, 46.45,
    ]
    rsi = rsi_14(closes)
    # Reference (Wilder, StockCharts): ~70.5 by bar 15, settles around 50-70
    assert 40.0 <= rsi <= 80.0


# ── pct_below_high ───────────────────────────────────────────────────────────

def test_pct_below_high_at_high():
    highs = [90, 95, 100, 98, 99]
    assert pct_below_high(100, highs, 5) == 0.0


def test_pct_below_high_known():
    highs = [100] * 20
    # 5% below high
    assert pct_below_high(95.0, highs, 20) == pytest.approx(5.0)


# ── dist_from_sma_pct ────────────────────────────────────────────────────────

def test_dist_from_sma_at_sma():
    closes = [100.0] * 20
    assert dist_from_sma_pct(100.0, closes, 20) == 0.0


def test_dist_from_sma_below():
    closes = [100.0] * 20
    # 5% below SMA
    assert dist_from_sma_pct(95.0, closes, 20) == pytest.approx(-5.0)


# ── volume_ratio ─────────────────────────────────────────────────────────────

def test_volume_ratio_double():
    vols = [1000] * 20
    assert volume_ratio(2000, vols) == 2.0


def test_volume_ratio_zero_avg():
    assert volume_ratio(1000, [0] * 20) == 0.0


# ── swing_low_high ───────────────────────────────────────────────────────────

def test_swing_low_high():
    lows = [10, 8, 12, 6, 9, 11]
    highs = [15, 18, 16, 20, 19, 17]
    lo, hi = swing_low_high(lows, highs, 5)
    assert lo == 6
    assert hi == 20


# ── pivot_s1_r1 ──────────────────────────────────────────────────────────────

def test_pivot_s1_r1_classic():
    # high=110, low=90, close=100 -> pivot=100, r1=110, s1=90
    s1, r1 = pivot_s1_r1(110, 90, 100)
    assert s1 == 90.0
    assert r1 == 110.0


# ── green_after_red ──────────────────────────────────────────────────────────

def test_green_after_red_true():
    # Two red days then a green
    closes = [105, 100, 95, 97]
    assert green_after_red(closes) is True


def test_green_after_red_false_only_one_red():
    closes = [100, 105, 95, 97]
    assert green_after_red(closes) is False


def test_green_after_red_false_today_red():
    closes = [105, 100, 95, 90]
    assert green_after_red(closes) is False


def test_green_after_red_too_short():
    assert green_after_red([100, 99, 98]) is False


# ── compute_signals integration ──────────────────────────────────────────────

def test_compute_signals_runs():
    closes = [100 + i * 0.1 for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000 + i * 10 for i in range(60)]
    s = compute_signals(closes, highs, lows, volumes)
    assert 0 <= s.rsi_14 <= 100
    assert s.pivot_resistance > s.pivot_support


def test_compute_signals_too_short_raises():
    with pytest.raises(ValueError):
        compute_signals([100.0], [101.0], [99.0], [1000])


# ── compute_score ────────────────────────────────────────────────────────────

def test_score_ideal_dip():
    """RSI=30 (max RSI bonus), 4% below 20D high (max), 3% below 20DMA (max),
    2x volume (max), green_after_red (max bonus) -> 100."""
    s = SignalsBundle(
        rsi_14=30.0,
        pct_below_20d_high=4.0,
        pct_below_50d_high=4.0,
        dist_from_20dma_pct=-3.0,
        dist_from_50dma_pct=-3.0,
        volume_ratio=2.0,
        swing_low_30d=0,
        swing_high_30d=0,
        pivot_support=0,
        pivot_resistance=0,
        green_after_red=True,
    )
    assert compute_score(s) == 100.0


def test_score_no_signals_zero():
    s = SignalsBundle(
        rsi_14=55.0,
        pct_below_20d_high=0.5,
        pct_below_50d_high=0.5,
        dist_from_20dma_pct=2.0,        # above SMA, no points
        dist_from_50dma_pct=2.0,
        volume_ratio=0.8,
        swing_low_30d=0,
        swing_high_30d=0,
        pivot_support=0,
        pivot_resistance=0,
        green_after_red=False,
    )
    assert compute_score(s) == 0.0


def test_score_capped_at_100():
    s = SignalsBundle(
        rsi_14=10.0,
        pct_below_20d_high=4.0,
        pct_below_50d_high=4.0,
        dist_from_20dma_pct=-3.0,
        dist_from_50dma_pct=-3.0,
        volume_ratio=2.0,
        swing_low_30d=0,
        swing_high_30d=0,
        pivot_support=0,
        pivot_resistance=0,
        green_after_red=True,
    )
    assert compute_score(s) <= 100.0


def test_score_partial():
    """RSI=35 -> 12.5, below_20d=6% -> 12.5, dist=0 (no contribution),
    vol=2 -> 20, green_after_red=False -> total 45."""
    s = SignalsBundle(
        rsi_14=35.0,
        pct_below_20d_high=6.0,
        pct_below_50d_high=6.0,
        dist_from_20dma_pct=0.0,  # outside the 1-5 band
        dist_from_50dma_pct=0.0,
        volume_ratio=2.0,
        swing_low_30d=0,
        swing_high_30d=0,
        pivot_support=0,
        pivot_resistance=0,
        green_after_red=False,
    )
    assert compute_score(s) == 45.0
