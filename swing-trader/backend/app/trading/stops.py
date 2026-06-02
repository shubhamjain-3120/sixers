def compute_stop(fill_price, atr_abs, cfg):
    """Return (sl_price, sl_pct, atr_pct). Pure — unit-testable, no I/O.

    sl_mode="atr": sl_pct = clamp(atr_sl_multiplier * atr_pct, sl_floor_pct, sl_cap_pct).
    Falls back to cfg.stop_loss_pct when mode is "fixed" or ATR is unavailable.
    """
    atr_pct = (atr_abs / fill_price * 100) if (atr_abs and fill_price) else None
    if cfg.sl_mode == "atr" and atr_pct:
        sl_pct = min(cfg.sl_cap_pct, max(cfg.sl_floor_pct, cfg.atr_sl_multiplier * atr_pct))
    else:
        sl_pct = cfg.stop_loss_pct
    sl_price = round(fill_price * (1 - sl_pct / 100), 1)
    return sl_price, sl_pct, atr_pct
