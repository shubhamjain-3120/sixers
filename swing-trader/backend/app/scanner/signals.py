from dataclasses import dataclass
from typing import List


@dataclass
class SignalsBundle:
    rsi_14: float
    pct_below_20d_high: float
    pct_below_50d_high: float
    dist_from_20dma_pct: float
    dist_from_50dma_pct: float
    volume_ratio: float
    swing_low_30d: float
    swing_high_30d: float
    pivot_support: float
    pivot_resistance: float
    green_after_red: bool


def rsi_14(closes: List[float]) -> float:
    """Wilder's RSI, 14 periods. Returns last value."""
    if len(closes) < 15:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    # First 14-period simple average
    avg_gain = sum(gains[:14]) / 14
    avg_loss = sum(losses[:14]) / 14

    # Wilder smoothing for remaining
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def pct_below_high(close_today: float, highs: List[float], window: int) -> float:
    slice_highs = highs[-window:]
    if not slice_highs:
        return 0.0
    h = max(slice_highs)
    if h == 0:
        return 0.0
    return (h - close_today) / h * 100


def dist_from_sma_pct(close_today: float, closes: List[float], window: int) -> float:
    if len(closes) < window:
        return 0.0
    sma = sum(closes[-window:]) / window
    if sma == 0:
        return 0.0
    return (close_today - sma) / sma * 100


def volume_ratio(vol_today: int, vols: List[int]) -> float:
    if len(vols) < 1:
        return 0.0
    recent = vols[-20:] if len(vols) >= 20 else vols
    avg = sum(recent) / len(recent)
    return vol_today / avg if avg > 0 else 0.0


def swing_low_high(lows: List[float], highs: List[float], window: int):
    slice_lows = lows[-window:]
    slice_highs = highs[-window:]
    return (min(slice_lows) if slice_lows else 0.0,
            max(slice_highs) if slice_highs else 0.0)


def pivot_s1_r1(prev_high: float, prev_low: float, prev_close: float):
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high
    return round(s1, 2), round(r1, 2)


def green_after_red(closes: List[float]) -> bool:
    if len(closes) < 4:
        return False
    today_green = closes[-1] > closes[-2]
    prior_red = all(closes[-i] < closes[-i - 1] for i in [2, 3])
    return today_green and prior_red


def compute_signals(closes: List[float], highs: List[float], lows: List[float],
                    volumes: List[int]) -> SignalsBundle:
    if len(closes) < 2:
        raise ValueError("Need at least 2 bars")

    close_today = closes[-1]
    rsi = rsi_14(closes)
    pb_20h = pct_below_high(close_today, highs, 20)
    pb_50h = pct_below_high(close_today, highs, 50)
    d20 = dist_from_sma_pct(close_today, closes, 20)
    d50 = dist_from_sma_pct(close_today, closes, 50)
    vol_r = volume_ratio(volumes[-1], volumes[:-1])
    sl30, sh30 = swing_low_high(lows, highs, 30)
    s1, r1 = pivot_s1_r1(highs[-2], lows[-2], closes[-2])
    gar = green_after_red(closes)

    return SignalsBundle(
        rsi_14=rsi,
        pct_below_20d_high=pb_20h,
        pct_below_50d_high=pb_50h,
        dist_from_20dma_pct=d20,
        dist_from_50dma_pct=d50,
        volume_ratio=vol_r,
        swing_low_30d=sl30,
        swing_high_30d=sh30,
        pivot_support=s1,
        pivot_resistance=r1,
        green_after_red=gar,
    )
