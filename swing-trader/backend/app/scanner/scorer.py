from app.scanner.signals import SignalsBundle


def compute_score(s: SignalsBundle) -> float:
    score = 0.0

    # RSI: peak at 30, 0 above 40
    if s.rsi_14 < 40:
        score += max(0, 25 * (40 - s.rsi_14) / 10)

    # Below 20D high: peak at 4%, range 2-8%
    p = s.pct_below_20d_high
    if 2 <= p <= 8:
        score += 25 * (1 - abs(p - 4) / 4)

    # Below 20DMA: peak at 3%, range 1-5%
    d = -s.dist_from_20dma_pct  # convert to positive distance
    if 1 <= d <= 5:
        score += 20 * (1 - abs(d - 3) / 2)

    # Volume ratio: peak at 2x, range 1.5-3x
    v = s.volume_ratio
    if 1.5 <= v <= 3.0:
        score += 20 * (1 - abs(v - 2.0) / 0.5)

    # Reversal confirmation bonus
    if s.green_after_red:
        score += 10

    return round(min(100, max(0, score)), 2)
