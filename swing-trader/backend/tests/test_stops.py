"""Unit tests for the ATR-based stop loss helper."""
import pytest
from types import SimpleNamespace
from app.trading.stops import compute_stop


def _cfg(sl_mode="atr", atr_sl_multiplier=2.5, sl_floor_pct=3.0, sl_cap_pct=6.0, stop_loss_pct=4.0):
    return SimpleNamespace(
        sl_mode=sl_mode,
        atr_sl_multiplier=atr_sl_multiplier,
        sl_floor_pct=sl_floor_pct,
        sl_cap_pct=sl_cap_pct,
        stop_loss_pct=stop_loss_pct,
    )


def test_atr_mid_range():
    """fill=1000, atr_abs=18 → atr_pct=1.8, raw=4.5 → sl_pct=4.5, sl_price≈955.0"""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, 18.0, _cfg())
    assert atr_pct == pytest.approx(1.8)
    assert sl_pct == pytest.approx(4.5)
    assert sl_price == pytest.approx(1000.0 * (1 - 4.5 / 100), abs=0.2)


def test_atr_clamps_to_floor():
    """atr_abs=8 → atr_pct=0.8, raw=2.0 → clamped to floor 3.0"""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, 8.0, _cfg())
    assert atr_pct == pytest.approx(0.8)
    assert sl_pct == pytest.approx(3.0)
    assert sl_price == pytest.approx(1000.0 * 0.97, abs=0.2)


def test_atr_clamps_to_cap():
    """atr_abs=40 → atr_pct=4.0, raw=10.0 → clamped to cap 6.0"""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, 40.0, _cfg())
    assert atr_pct == pytest.approx(4.0)
    assert sl_pct == pytest.approx(6.0)
    assert sl_price == pytest.approx(1000.0 * 0.94, abs=0.2)


def test_fixed_mode_ignores_atr():
    """sl_mode='fixed' uses stop_loss_pct regardless of ATR."""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, 18.0, _cfg(sl_mode="fixed"))
    assert sl_pct == pytest.approx(4.0)
    assert sl_price == pytest.approx(1000.0 * 0.96, abs=0.2)


def test_atr_none_falls_back_to_fixed():
    """atr_abs=None with mode='atr' falls back to stop_loss_pct."""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, None, _cfg())
    assert atr_pct is None
    assert sl_pct == pytest.approx(4.0)
    assert sl_price == pytest.approx(1000.0 * 0.96, abs=0.2)


def test_atr_zero_falls_back_to_fixed():
    """atr_abs=0 (falsy) with mode='atr' falls back to stop_loss_pct."""
    sl_price, sl_pct, atr_pct = compute_stop(1000.0, 0.0, _cfg())
    assert atr_pct is None
    assert sl_pct == pytest.approx(4.0)
