from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.session import get_db
from app.db.models import Trade, Config, SetupClassification, OhlcvDaily
from app.schemas.trades import TradeEntryRequest, TradeEntryResponse, OpenPositionRow, ClosedTradeRow, TradeDetail, OhlcvBar
from typing import List
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["trades"])


@router.get("/api/trades/open", response_model=List[OpenPositionRow])
def get_open_trades(db: Session = Depends(get_db)):
    from app.kite.client import get_kite_client
    trades = db.query(Trade).filter(Trade.status == "OPEN").order_by(desc(Trade.entry_date)).all()
    if not trades:
        return []

    # Fetch live LTP for all open symbols in one batch call
    ltp_map: dict = {}
    try:
        kite = get_kite_client(db)
        if kite:
            keys = [f"NSE:{t.symbol}" for t in trades]
            raw = kite.ltp(keys)
            ltp_map = {k.replace("NSE:", ""): v["last_price"] for k, v in raw.items()}
    except Exception as e:
        logger.warning(f"LTP fetch for open positions failed: {e}")

    result = []
    for t in trades:
        days = (date.today() - t.entry_date.date()).days
        ltp = ltp_map.get(t.symbol)
        pnl_pct = ((ltp - t.entry_price) / t.entry_price * 100) if ltp else None
        pnl_inr = ((ltp - t.entry_price) * t.qty) if ltp else None
        pct_to_target = ((t.initial_target_price - ltp) / ltp * 100) if (ltp and t.initial_target_price) else None
        pct_to_sl = ((t.current_sl_price - ltp) / ltp * 100) if (ltp and t.current_sl_price) else None
        result.append(OpenPositionRow(
            id=t.id,
            symbol=t.symbol,
            segment=t.segment,
            entry_date=t.entry_date,
            entry_price=t.entry_price,
            ltp=ltp,
            pnl_pct=pnl_pct,
            pnl_inr=pnl_inr,
            initial_target_price=t.initial_target_price,
            current_sl_price=t.current_sl_price,
            pct_to_target=pct_to_target,
            pct_to_sl=pct_to_sl,
            trailing_state=t.trailing_state or "initial",
            days_held=days,
        ))
    return result


@router.get("/api/trades/closed", response_model=List[ClosedTradeRow])
def get_closed_trades(db: Session = Depends(get_db)):
    return db.query(Trade).filter(Trade.status == "CLOSED").order_by(desc(Trade.exit_date)).all()


@router.get("/api/trades/{trade_id}", response_model=TradeDetail)
def get_trade_detail(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="trade_not_found")

    # Fetch OHLCV from entry date to exit date (or today for open trades)
    from datetime import date as date_cls
    start = trade.entry_date.date()
    end = trade.exit_date.date() if trade.exit_date else date_cls.today()

    bars = (
        db.query(OhlcvDaily)
        .filter(OhlcvDaily.symbol == trade.symbol, OhlcvDaily.date >= start, OhlcvDaily.date <= end)
        .order_by(OhlcvDaily.date)
        .all()
    )

    return TradeDetail(
        id=trade.id,
        symbol=trade.symbol,
        segment=trade.segment,
        entry_date=trade.entry_date,
        exit_date=trade.exit_date,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        qty=trade.qty,
        capital_deployed=trade.capital_deployed,
        initial_target_price=trade.initial_target_price,
        initial_sl_price=trade.initial_sl_price,
        current_sl_price=trade.current_sl_price,
        high_water_mark=trade.high_water_mark,
        trailing_state=trade.trailing_state,
        pnl_inr=trade.pnl_inr,
        pnl_pct=trade.pnl_pct,
        exit_reason=trade.exit_reason,
        days_held=trade.days_held,
        badge_at_entry=trade.badge_at_entry,
        llm_verdict_at_entry=trade.llm_verdict_at_entry,
        pullback_score_at_entry=trade.pullback_score_at_entry,
        shubham_score_at_entry=trade.shubham_score_at_entry,
        notes=trade.notes,
        ltp_at_entry=trade.ltp_at_entry,
        rsi_at_entry=trade.rsi_at_entry,
        pct_below_20d_high_at_entry=trade.pct_below_20d_high_at_entry,
        pct_below_50d_high_at_entry=trade.pct_below_50d_high_at_entry,
        dist_from_20dma_at_entry=trade.dist_from_20dma_at_entry,
        dist_from_50dma_at_entry=trade.dist_from_50dma_at_entry,
        volume_ratio_at_entry=trade.volume_ratio_at_entry,
        swing_low_at_entry=trade.swing_low_at_entry,
        swing_high_at_entry=trade.swing_high_at_entry,
        pivot_support_at_entry=trade.pivot_support_at_entry,
        pivot_resistance_at_entry=trade.pivot_resistance_at_entry,
        green_after_red_at_entry=trade.green_after_red_at_entry,
        ohlcv=[OhlcvBar(date=b.date, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume) for b in bars],
    )


@router.post("/api/trades", response_model=TradeEntryResponse)
def place_trade(body: TradeEntryRequest, db: Session = Depends(get_db)):
    from app.trading.entry import execute_entry
    from app.kite.auth import get_valid_token

    token = get_valid_token(db)
    if not token:
        raise HTTPException(status_code=401, detail="kite_session_expired")

    # Concurrent positions check
    today = date.today()
    cfg = db.query(Config).filter(Config.id == 1).first()
    open_count = db.query(Trade).filter(Trade.status == "OPEN").count()
    if cfg and open_count >= cfg.max_concurrent_positions:
        raise HTTPException(status_code=400, detail="max_positions_reached")

    verdict_val = None
    from app.db.models import NewsClassification
    nc = (
        db.query(NewsClassification)
        .filter(NewsClassification.symbol == body.symbol, NewsClassification.classification_date == today)
        .first()
    )
    verdict_val = nc.verdict if nc else None

    try:
        result = execute_entry(db, body.symbol, badge=None, llm_verdict=verdict_val, custom_capital=body.custom_capital)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        err_str = str(e)
        # Zerodha IP whitelist rejection — surface as 403 with the Kite message
        if "not allowed to place orders" in err_str or "PermissionException" in type(e).__name__:
            raise HTTPException(status_code=403, detail=f"Zerodha blocked the order: {err_str}")
        logger.error(f"Order placement error for {body.symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Kite API error: {err_str}")

    if result is None:
        raise HTTPException(status_code=200, detail="not_filled")
    return result


@router.post("/api/trades/{trade_id}/retry-gtt")
def retry_gtt(trade_id: int, db: Session = Depends(get_db)):
    """For a FAILED trade where the buy filled but GTT placement failed — retry GTT only."""
    from app.kite.auth import get_valid_token
    from app.kite.client import get_kite_client
    from app.kite.gtt import place_oco_gtt

    token = get_valid_token(db)
    if not token:
        raise HTTPException(status_code=401, detail="kite_session_expired")

    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.status == "FAILED").first()
    if not trade:
        raise HTTPException(status_code=404, detail="failed_trade_not_found")
    if not trade.entry_price or not trade.qty:
        raise HTTPException(status_code=400, detail="trade_missing_fill_data")

    kite = get_kite_client(db)
    if not kite:
        raise HTTPException(status_code=401, detail="kite_session_expired")

    cfg = db.query(Config).filter(Config.id == 1).first()
    target_price = trade.initial_target_price or round(trade.entry_price * (1 + cfg.target_pct / 100), 1)
    sl_price = trade.initial_sl_price or round(trade.entry_price * (1 - cfg.stop_loss_pct / 100), 1)

    try:
        ltp_data = kite.ltp([f"NSE:{trade.symbol}"])
        ltp = ltp_data[f"NSE:{trade.symbol}"]["last_price"]
        gtt_id = place_oco_gtt(
            kite, db, trade.id, trade.symbol, trade.qty,
            sl_price, target_price, ltp, trade.gtt_tag,
        )
        trade.active_gtt_id = gtt_id
        trade.status = "OPEN"
        trade.notes = None
        db.commit()
        logger.info(f"GTT retry succeeded for trade {trade_id}: gtt_id={gtt_id}")
        return {"status": "gtt_placed", "gtt_id": gtt_id, "trade_id": trade_id}
    except Exception as e:
        err_str = str(e)
        logger.error(f"GTT retry failed for trade {trade_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"GTT placement failed: {err_str}")


@router.post("/api/trades/{trade_id}/force-exit")
def force_exit(trade_id: int, db: Session = Depends(get_db)):
    from app.trading.entry import execute_force_exit
    from app.kite.auth import get_valid_token

    token = get_valid_token(db)
    if not token:
        raise HTTPException(status_code=401, detail="kite_session_expired")

    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.status == "OPEN").first()
    if not trade:
        raise HTTPException(status_code=404, detail="trade_not_found")

    try:
        execute_force_exit(db, trade)
    except Exception as e:
        err_str = str(e)
        if "not allowed to place orders" in err_str or "PermissionException" in type(e).__name__:
            raise HTTPException(status_code=403, detail=f"Zerodha blocked the order: {err_str}")
        logger.error(f"Force exit error for trade {trade_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Kite API error: {err_str}")
    return {"status": "exit_placed", "trade_id": trade_id}
