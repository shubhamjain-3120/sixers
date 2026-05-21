from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
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
    cfg_row = db.query(DailyScan).order_by(desc(DailyScan.scan_date)).first()
    last_scan = cfg_row.scan_date.isoformat() if cfg_row else None
    count = db.query(DailyScan).filter(DailyScan.scan_date == date.today()).count()
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
    if scan_date is None:
        latest = db.query(DailyScan.scan_date).order_by(desc(DailyScan.scan_date)).first()
        if not latest:
            return []
        scan_date = latest[0]

    from app.db.models import Config
    cfg = db.query(Config).filter(Config.id == 1).first()
    min_score = cfg.min_score_threshold if cfg else 60.0

    scans = (
        db.query(DailyScan)
        .filter(DailyScan.scan_date == scan_date, DailyScan.score >= min_score)
        .order_by(desc(DailyScan.score))
        .all()
    )

    result = []
    for s in scans:
        inst = db.query(Instrument).filter(Instrument.symbol == s.symbol).first()
        setup = (
            db.query(SetupClassification)
            .filter(
                SetupClassification.symbol == s.symbol,
                SetupClassification.scan_date == scan_date,
            )
            .first()
        )
        news_cls = (
            db.query(NewsClassification)
            .filter(
                NewsClassification.symbol == s.symbol,
                NewsClassification.classification_date == scan_date,
            )
            .first()
        )

        badge = setup.badge if setup else "YELLOW"
        if not include_red and badge == "RED":
            continue

        # sparkline: last 30 closes from ohlcv_daily
        ohlcv_rows = (
            db.query(OhlcvDaily)
            .filter(OhlcvDaily.symbol == s.symbol)
            .order_by(desc(OhlcvDaily.date))
            .limit(30)
            .all()
        )
        sparkline = [r.close for r in reversed(ohlcv_rows)]

        pct_change = None
        if s.ltp and s.prev_close and s.prev_close > 0:
            pct_change = (s.ltp - s.prev_close) / s.prev_close * 100

        # Support / resistance % away from LTP
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
                sparkline_data=sparkline,
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
    sym = symbol.upper()
    latest_scan = (
        db.query(DailyScan)
        .filter(DailyScan.symbol == sym)
        .order_by(desc(DailyScan.scan_date))
        .first()
    )
    if not latest_scan:
        raise HTTPException(status_code=404, detail="no_scan_data")

    inst = db.query(Instrument).filter(Instrument.symbol == sym).first()
    setup = (
        db.query(SetupClassification)
        .filter(SetupClassification.symbol == sym, SetupClassification.scan_date == latest_scan.scan_date)
        .first()
    )

    badge = setup.badge if setup else "YELLOW"

    pct_change = None
    if latest_scan.ltp and latest_scan.prev_close and latest_scan.prev_close > 0:
        pct_change = (latest_scan.ltp - latest_scan.prev_close) / latest_scan.prev_close * 100

    support_pct = None
    if latest_scan.pivot_support and latest_scan.ltp and latest_scan.ltp > 0:
        support_pct = (latest_scan.pivot_support - latest_scan.ltp) / latest_scan.ltp * 100
    resistance_pct = None
    if latest_scan.pivot_resistance and latest_scan.ltp and latest_scan.ltp > 0:
        resistance_pct = (latest_scan.pivot_resistance - latest_scan.ltp) / latest_scan.ltp * 100

    high_20d = None
    if latest_scan.ltp and latest_scan.pct_below_20d_high:
        high_20d = latest_scan.ltp / (1 - latest_scan.pct_below_20d_high / 100)

    sparkline_rows = (
        db.query(OhlcvDaily)
        .filter(OhlcvDaily.symbol == sym)
        .order_by(desc(OhlcvDaily.date))
        .limit(30)
        .all()
    )
    sparkline = [r.close for r in reversed(sparkline_rows)]

    news_cls = (
        db.query(NewsClassification)
        .filter(
            NewsClassification.symbol == sym,
            NewsClassification.classification_date == latest_scan.scan_date,
        )
        .first()
    )

    import json as _json
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
        ltp=latest_scan.ltp,
        prev_close=latest_scan.prev_close,
        pct_change_today=pct_change,
        high_20d=high_20d,
        pct_below_20d_high=latest_scan.pct_below_20d_high,
        pct_below_50d_high=latest_scan.pct_below_50d_high,
        dist_from_20dma_pct=latest_scan.dist_from_20dma_pct,
        dist_from_50dma_pct=latest_scan.dist_from_50dma_pct,
        volume_ratio=latest_scan.volume_ratio,
        swing_low_30d=latest_scan.swing_low_30d,
        swing_high_30d=latest_scan.swing_high_30d,
        support=latest_scan.pivot_support,
        support_pct_away=support_pct,
        resistance=latest_scan.pivot_resistance,
        resistance_pct_away=resistance_pct,
        rsi_14=latest_scan.rsi_14,
        score=latest_scan.score,
        green_after_red=latest_scan.green_after_red,
        sparkline_data=sparkline,
        badge=badge,
        llm_summary=news_cls.summary if news_cls else None,
        news_verdict=news_cls.verdict if news_cls else None,
        news_confidence=news_cls.confidence if news_cls else None,
        news_headlines=per_headlines,
        scan_date=latest_scan.scan_date,
    )
