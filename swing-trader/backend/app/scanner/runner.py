import logging
import time
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.db.models import Instrument, Blacklist, OhlcvDaily, DailyScan, Config
from app.kite.client import get_kite_client
from app.scanner.signals import compute_signals
from app.scanner.scorer import compute_score

logger = logging.getLogger(__name__)

_scan_running = False


def run_daily_scan():
    global _scan_running
    if _scan_running:
        logger.warning("Scan already running, skipping")
        return
    _scan_running = True
    db = SessionLocal()
    try:
        _do_scan(db)
    except Exception as e:
        logger.error(f"Daily scan failed: {e}", exc_info=True)
    finally:
        _scan_running = False
        db.close()


def _do_scan(db: Session):
    logger.info("Starting daily scan")
    kite = get_kite_client(db)
    if not kite:
        logger.error("No Kite session for scan; aborting")
        return

    blacklisted = {b.symbol for b in db.query(Blacklist).all()}
    instruments = db.query(Instrument).all()
    today = date.today()
    from_date = (datetime.today() - timedelta(days=90)).date()

    for inst in instruments:
        if inst.symbol in blacklisted:
            logger.info(f"Skipping blacklisted {inst.symbol}")
            continue
        if not inst.kite_instrument_token:
            logger.warning(f"No instrument token for {inst.symbol}; skipping")
            continue

        try:
            candles = kite.historical_data(
                inst.kite_instrument_token,
                from_date,
                today,
                "day",
            )
        except Exception as e:
            logger.error(f"Historical data fetch failed for {inst.symbol}: {e}")
            continue

        if len(candles) < 22:
            logger.warning(f"Not enough data for {inst.symbol} ({len(candles)} bars)")
            continue

        # Upsert OHLCV
        for c in candles:
            bar_date = c["date"].date() if hasattr(c["date"], "date") else c["date"]
            existing = (
                db.query(OhlcvDaily)
                .filter(OhlcvDaily.symbol == inst.symbol, OhlcvDaily.date == bar_date)
                .first()
            )
            if existing:
                existing.open = c["open"]
                existing.high = c["high"]
                existing.low = c["low"]
                existing.close = c["close"]
                existing.volume = c["volume"]
            else:
                db.add(OhlcvDaily(
                    symbol=inst.symbol, date=bar_date,
                    open=c["open"], high=c["high"], low=c["low"],
                    close=c["close"], volume=c["volume"],
                ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c["volume"] for c in candles]

        try:
            signals = compute_signals(closes, highs, lows, volumes)
            score = compute_score(signals)
        except Exception as e:
            logger.error(f"Signal compute failed for {inst.symbol}: {e}")
            continue

        # Upsert DailyScan row
        existing_scan = (
            db.query(DailyScan)
            .filter(DailyScan.symbol == inst.symbol, DailyScan.scan_date == today)
            .first()
        )
        ltp = closes[-1]
        prev_close = closes[-2] if len(closes) >= 2 else closes[-1]

        row_data = dict(
            ltp=ltp,
            prev_close=prev_close,
            rsi_14=signals.rsi_14,
            pct_below_20d_high=signals.pct_below_20d_high,
            pct_below_50d_high=signals.pct_below_50d_high,
            dist_from_20dma_pct=signals.dist_from_20dma_pct,
            dist_from_50dma_pct=signals.dist_from_50dma_pct,
            volume_ratio=signals.volume_ratio,
            swing_low_30d=signals.swing_low_30d,
            swing_high_30d=signals.swing_high_30d,
            pivot_support=signals.pivot_support,
            pivot_resistance=signals.pivot_resistance,
            green_after_red=signals.green_after_red,
            score=score,
        )

        if existing_scan:
            for k, v in row_data.items():
                setattr(existing_scan, k, v)
        else:
            db.add(DailyScan(symbol=inst.symbol, scan_date=today, **row_data))

        try:
            db.commit()
        except IntegrityError:
            db.rollback()

        logger.debug(f"{inst.symbol}: score={score:.1f} RSI={signals.rsi_14:.1f}")

    logger.info("Daily scan complete")


def revalidate_candidates(db: Session, kite):
    """Refresh LTP for yesterday's candidates without re-running LLM."""
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    cfg = db.query(Config).filter(Config.id == 1).first()
    min_score = cfg.min_score_threshold if cfg else 60.0

    scans = (
        db.query(DailyScan)
        .filter(DailyScan.scan_date == yesterday, DailyScan.score >= min_score)
        .all()
    )
    if not scans:
        return

    symbols = [f"NSE:{s.symbol}" for s in scans]
    try:
        ltp_data = kite.ltp(symbols)
    except Exception as e:
        logger.error(f"LTP batch fetch failed during revalidation: {e}")
        return

    for s in scans:
        key = f"NSE:{s.symbol}"
        if key in ltp_data:
            ltp = ltp_data[key].get("last_price")
            if ltp:
                s.ltp = ltp
                if s.prev_close and s.prev_close > 0:
                    pass  # pct_change derived on read
    db.commit()
    logger.info(f"Revalidated {len(scans)} candidates")
