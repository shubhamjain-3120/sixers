from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db.session import get_db
from app.db.models import DailyScan, Instrument, SetupClassification, NewsClassification, OhlcvDaily, BlockDeal
from app.schemas.scan import CandidateRow, ScanStatus, OhlcvBar, BlockDealOut, CandidateDetail, PerHeadline
from typing import List, Optional
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scan", tags=["scan"])

@router.get("/status", response_model=ScanStatus)
def scan_status(db: Session = Depends(get_db)):
    from app.scanner import runner
    row = db.query(
        func.max(DailyScan.scan_date).label("last_date"),
        func.count(DailyScan.id).filter(DailyScan.scan_date == date.today()).label("today_count"),
    ).first()
    last_scan = row.last_date.isoformat() if row and row.last_date else None
    count = row.today_count if row else 0
    return ScanStatus(last_scan_at=last_scan, candidate_count=count, running=runner._scan_running)


@router.post("/run")
def trigger_scan():
    from app.scanner.runner import run_daily_scan
    import threading
    t = threading.Thread(target=run_daily_scan, daemon=True)
    t.start()
    return {"status": "scan_started"}


@router.get("/candidates", response_model=List[CandidateRow])
def get_candidates(
    scan_date: Optional[date] = None,
    include_red: bool = False,
    db: Session = Depends(get_db)
):
    from sqlalchemy import and_
    from app.db.models import Config

    # Two queries: config + one joined query for all candidate data
    cfg_row = db.query(Config.min_score_threshold, Config.min_shubham_score_threshold).filter(Config.id == 1).first()
    min_score = cfg_row.min_score_threshold if cfg_row and cfg_row.min_score_threshold is not None else 60.0
    min_shubham = cfg_row.min_shubham_score_threshold if cfg_row and cfg_row.min_shubham_score_threshold is not None else 60.0

    if scan_date is None:
        scan_date = db.query(func.max(DailyScan.scan_date)).scalar()
        if not scan_date:
            return []

    rows = (
        db.query(DailyScan, Instrument, SetupClassification, NewsClassification)
        .outerjoin(Instrument, Instrument.symbol == DailyScan.symbol)
        .outerjoin(
            SetupClassification,
            and_(
                SetupClassification.symbol == DailyScan.symbol,
                SetupClassification.scan_date == scan_date,
            ),
        )
        .outerjoin(
            NewsClassification,
            and_(
                NewsClassification.symbol == DailyScan.symbol,
                NewsClassification.classification_date == scan_date,
            ),
        )
        .filter(
            DailyScan.scan_date == scan_date,
            DailyScan.score >= min_score,
            DailyScan.shubham_score >= min_shubham,
        )
        .order_by(desc(DailyScan.shubham_score), desc(DailyScan.score))
        .all()
    )

    result = []
    for s, inst, setup, news_cls in rows:
        badge = setup.badge if setup else "YELLOW"
        if not include_red and badge == "RED":
            continue

        pct_change = None
        if s.ltp and s.prev_close and s.prev_close > 0:
            pct_change = (s.ltp - s.prev_close) / s.prev_close * 100

        support_pct = None
        if s.pivot_support and s.ltp and s.ltp > 0:
            support_pct = (s.pivot_support - s.ltp) / s.ltp * 100
        resistance_pct = None
        if s.pivot_resistance and s.ltp and s.ltp > 0:
            resistance_pct = (s.pivot_resistance - s.ltp) / s.ltp * 100

        high_20d = None
        if s.ltp and s.pct_below_20d_high:
            high_20d = s.ltp / (1 - s.pct_below_20d_high / 100)

        result.append(
            CandidateRow(
                symbol=s.symbol,
                name=inst.name if inst else None,
                segment=inst.segment if inst else "NIFTY50_STOCK",
                ltp=s.ltp,
                prev_close=s.prev_close,
                pct_change_today=pct_change,
                high_20d=high_20d,
                pct_below_20d_high=s.pct_below_20d_high,
                support=s.pivot_support,
                support_pct_away=support_pct,
                resistance=s.pivot_resistance,
                resistance_pct_away=resistance_pct,
                rsi_14=s.rsi_14,
                score=s.score,
                shubham_score=s.shubham_score,
                dist_from_20dma_pct=s.dist_from_20dma_pct,
                dist_from_50dma_pct=s.dist_from_50dma_pct,
                sparkline_data=[],
                badge=badge,
                llm_summary=news_cls.summary if news_cls else None,
                scan_date=s.scan_date,
            )
        )
    return result


@router.get("/ohlcv/{symbol}", response_model=List[OhlcvBar])
def get_ohlcv(symbol: str, days: int = 90, db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(OhlcvDaily)
        .filter(OhlcvDaily.symbol == symbol.upper(), OhlcvDaily.date >= since)
        .order_by(OhlcvDaily.date)
        .all()
    )
    return [OhlcvBar(date=r.date, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume) for r in rows]


@router.get("/block-deals/{symbol}", response_model=List[BlockDealOut])
def get_block_deals(symbol: str, days: int = 5, db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days * 2)  # cover weekends
    rows = (
        db.query(BlockDeal)
        .filter(BlockDeal.symbol == symbol.upper(), BlockDeal.deal_date >= since)
        .order_by(desc(BlockDeal.deal_date))
        .limit(20)
        .all()
    )
    return [
        BlockDealOut(
            deal_date=r.deal_date,
            client_name=r.client_name,
            deal_type=r.deal_type,
            quantity=r.quantity,
            price=r.price,
            source=r.source,
        )
        for r in rows
    ]


@router.get("/detail/{symbol}", response_model=CandidateDetail)
def get_candidate_detail(symbol: str, db: Session = Depends(get_db)):
    from sqlalchemy import and_
    import json as _json

    sym = symbol.upper()

    # Single JOIN query: latest scan + instrument + badge + news
    latest_scan_sq = (
        db.query(func.max(DailyScan.scan_date))
        .filter(DailyScan.symbol == sym)
        .scalar_subquery()
    )
    row = (
        db.query(DailyScan, Instrument, SetupClassification, NewsClassification)
        .outerjoin(Instrument, Instrument.symbol == DailyScan.symbol)
        .outerjoin(
            SetupClassification,
            and_(
                SetupClassification.symbol == DailyScan.symbol,
                SetupClassification.scan_date == DailyScan.scan_date,
            ),
        )
        .outerjoin(
            NewsClassification,
            and_(
                NewsClassification.symbol == DailyScan.symbol,
                NewsClassification.classification_date == DailyScan.scan_date,
            ),
        )
        .filter(DailyScan.symbol == sym, DailyScan.scan_date == latest_scan_sq)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="no_scan_data")

    s, inst, setup, news_cls = row
    badge = setup.badge if setup else "YELLOW"

    pct_change = None
    if s.ltp and s.prev_close and s.prev_close > 0:
        pct_change = (s.ltp - s.prev_close) / s.prev_close * 100

    support_pct = None
    if s.pivot_support and s.ltp and s.ltp > 0:
        support_pct = (s.pivot_support - s.ltp) / s.ltp * 100
    resistance_pct = None
    if s.pivot_resistance and s.ltp and s.ltp > 0:
        resistance_pct = (s.pivot_resistance - s.ltp) / s.ltp * 100

    high_20d = None
    if s.ltp and s.pct_below_20d_high:
        high_20d = s.ltp / (1 - s.pct_below_20d_high / 100)

    per_headlines: list[PerHeadline] = []
    if news_cls and news_cls.per_headline_json and news_cls.headlines_json:
        try:
            raw_ph = _json.loads(news_cls.per_headline_json)
            headlines_list = _json.loads(news_cls.headlines_json)
            for ph in raw_ph:
                idx = ph.get("idx", 1) - 1
                headline_text = headlines_list[idx] if idx < len(headlines_list) else ""
                per_headlines.append(PerHeadline(
                    idx=ph.get("idx", 1),
                    headline=headline_text,
                    classification=ph.get("classification", ""),
                    reason=ph.get("reason", ""),
                ))
        except Exception:
            pass

    return CandidateDetail(
        symbol=sym,
        name=inst.name if inst else None,
        segment=inst.segment if inst else "NIFTY50_STOCK",
        sector=inst.sector if inst else None,
        ltp=s.ltp,
        prev_close=s.prev_close,
        pct_change_today=pct_change,
        high_20d=high_20d,
        pct_below_20d_high=s.pct_below_20d_high,
        pct_below_50d_high=s.pct_below_50d_high,
        dist_from_20dma_pct=s.dist_from_20dma_pct,
        dist_from_50dma_pct=s.dist_from_50dma_pct,
        volume_ratio=s.volume_ratio,
        swing_low_30d=s.swing_low_30d,
        swing_high_30d=s.swing_high_30d,
        support=s.pivot_support,
        support_pct_away=support_pct,
        resistance=s.pivot_resistance,
        resistance_pct_away=resistance_pct,
        rsi_14=s.rsi_14,
        score=s.score,
        shubham_score=s.shubham_score,
        green_after_red=s.green_after_red,
        sparkline_data=[],
        badge=badge,
        llm_summary=news_cls.summary if news_cls else None,
        news_verdict=news_cls.verdict if news_cls else None,
        news_confidence=news_cls.confidence if news_cls else None,
        news_headlines=per_headlines,
        scan_date=s.scan_date,
    )


@router.get("/ltp")
def get_live_ltp(symbols: str = Query(...), db: Session = Depends(get_db)):
    from app.kite.client import get_kite_client
    kite = get_kite_client(db)
    if not kite:
        raise HTTPException(status_code=503, detail="Kite not connected")
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    keys = [f"NSE:{s}" for s in sym_list]
    try:
        raw = kite.ltp(keys)
        return {k.replace("NSE:", ""): v["last_price"] for k, v in raw.items()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
