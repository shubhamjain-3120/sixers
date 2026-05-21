from app.scanner.signals import SignalsBundle


def compute_score(s: SignalsBundle) -> float:
    """Pullback Score — rewards oversold mean-reversion setups (deeper RSI dip,
    pullback below 20DMA, elevated volume). Tuned for 2–4 week swing holds."""
    score = 0.0

    # RSI: peak at 30, 0 above 40
    if s.rsi_14 < 40:
        score += max(0, 15 * (40 - s.rsi_14) / 10)

    # Below 20D high: peak at 4%, range 2-10%
    p = s.pct_below_20d_high
    if 2 <= p <= 10:
        score += 30 * (1 - abs(p - 4) / 6)

    # Below 20DMA: peak at 3%, range 1-5%
    d = -s.dist_from_20dma_pct  # convert to positive distance
    if 1 <= d <= 5:
        score += 20 * (1 - abs(d - 3) / 2)

    # Volume ratio: peak at 2x, range 1.5-3x
    v = s.volume_ratio
    if 1.5 <= v <= 3.0:
        score += 25 * (1 - abs(v - 2.0) / 0.5)

    # Reversal confirmation bonus
    if s.green_after_red:
        score += 10

    return round(min(100, max(0, score)), 2)


def compute_shubham_score(s: SignalsBundle) -> float:
    """Shubham Score — tuned to the user's actual realized trades (backtest of
    2024–25 personal trade log): shallow pullbacks on quality large-caps held
    1–5 days for ~2% gains. Rewards mid-range RSI, mild dip from 20D high,
    proximity to 20DMA, and avoids exhausted/overbought tape."""
    score = 0.0

    # RSI sweet spot: peak at 47, range 35-60. Penalizes both oversold (panic)
    # and overbought (>65) tape.
    r = s.rsi_14
    if 35 <= r <= 60:
        score += 25 * (1 - abs(r - 47) / 13)

    # Pullback below 20D high: peak at 5%, range 0-10% (wider/shallower than
    # the Pullback Score's 4% peak).
    p = s.pct_below_20d_high
    if 0 <= p <= 10:
        score += 25 * (1 - abs(p - 5) / 5)

    # Near 20DMA: peak at -0.5%, range -3% to +3% (you bought near the MA, not
    # deep below it).
    d = s.dist_from_20dma_pct
    if -3 <= d <= 3:
        score += 25 * (1 - abs(d - (-0.5)) / 3)

    # Volume: peak at 1.5x, range 0.5-3x. Low floor — you traded fine without
    # heavy volume confirmation.
    v = s.volume_ratio
    if 0.5 <= v <= 3.0:
        score += 15 * (1 - abs(v - 1.5) / 1.5)

    # Reversal confirmation bonus
    if s.green_after_red:
        score += 10

    return round(min(100, max(0, score)), 2)
