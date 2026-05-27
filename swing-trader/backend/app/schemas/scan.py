from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class CandidateRow(BaseModel):
    symbol: str
    name: Optional[str] = None
    segment: str
    ltp: Optional[float] = None
    prev_close: Optional[float] = None
    pct_change_today: Optional[float] = None
    high_20d: Optional[float] = None
    pct_below_20d_high: Optional[float] = None
    dist_from_20dma_pct: Optional[float] = None
    dist_from_50dma_pct: Optional[float] = None
    support: Optional[float] = None
    support_pct_away: Optional[float] = None
    resistance: Optional[float] = None
    resistance_pct_away: Optional[float] = None
    rsi_14: Optional[float] = None
    score: float
    shubham_score: Optional[float] = None
    sparkline_data: List[float] = []
    llm_summary: Optional[str] = None
    scan_date: date

    class Config:
        from_attributes = True


class PerHeadline(BaseModel):
    idx: int
    headline: str
    classification: str  # NOISE | FUNDAMENTAL_NEGATIVE | FUNDAMENTAL_POSITIVE | IRRELEVANT
    reason: str
    published_at: Optional[str] = None


class CandidateDetail(CandidateRow):
    sector: Optional[str] = None
    pct_below_50d_high: Optional[float] = None
    volume_ratio: Optional[float] = None
    swing_low_30d: Optional[float] = None
    swing_high_30d: Optional[float] = None
    green_after_red: Optional[bool] = None
    news_verdict: Optional[str] = None       # NOISE | FUNDAMENTAL_RISK | MIXED | INSUFFICIENT_DATA
    news_confidence: Optional[float] = None
    news_headlines: List[PerHeadline] = []


class ScanStatus(BaseModel):
    last_scan_at: Optional[str] = None
    candidate_count: int
    running: bool


class OhlcvBar(BaseModel):
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


