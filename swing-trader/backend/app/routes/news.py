from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/news", tags=["news"])


@router.post("/classify")
def trigger_news_classify():
    """Manual trigger for the full news classification pipeline (all today's candidates)."""
    from app.news.classifier import run_news_classification
    import threading
    t = threading.Thread(target=run_news_classification, daemon=True)
    t.start()
    return {"status": "classification_started"}


class TestClassifyRequest(BaseModel):
    symbol: str
    company_name: str = ""
    sector: str = "Unknown"
    headlines: List[str]
    block_flag: bool = False
    sector_flag: bool = False
    ltp: float = 100.0
    pct_drop: float = 3.0


@router.post("/test-classify")
def test_classify(req: TestClassifyRequest, db: Session = Depends(get_db)):
    """
    Classify a set of custom headlines without caching or persisting.
    Used for M6 acceptance testing. Returns verdict, confidence, summary, badge,
    and per-headline classifications.
    """
    from datetime import datetime, timezone
    from app.news.classifier import classify_news, finalize_badge
    from app.db.models import NewsClassification
    from datetime import date
    import json

    test_date = date(2099, 1, 1)  # far-future date so it never collides with real data

    # Delete any prior test row for this symbol at test_date
    db.query(NewsClassification).filter(
        NewsClassification.symbol == req.symbol,
        NewsClassification.classification_date == test_date,
    ).delete()
    db.commit()

    headlines = [
        (h, datetime.now(timezone.utc).replace(tzinfo=None), "")
        for h in req.headlines
    ]

    result = classify_news(
        symbol=req.symbol,
        name=req.company_name or req.symbol,
        sector=req.sector,
        headlines=headlines,
        ltp=req.ltp,
        pct_drop=req.pct_drop,
        n_sessions=5,
        sector_index_name="NIFTY 50",
        sector_change_pct=0.0,
        scan_date=test_date,
        db=db,
    )

    # Clean up test row
    db.query(NewsClassification).filter(
        NewsClassification.symbol == req.symbol,
        NewsClassification.classification_date == test_date,
    ).delete()
    db.commit()

    badge = finalize_badge(req.block_flag, req.sector_flag, result["verdict"])

    return {
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "summary": result["summary"],
        "per_headline": result["per_headline"],
        "badge": badge,
        "block_flag": req.block_flag,
        "sector_flag": req.sector_flag,
    }
