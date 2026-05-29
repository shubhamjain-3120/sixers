from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date as date_type


class OhlcvBar(BaseModel):
    date: date_type
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None

    class Config:
        from_attributes = True


class TradeEntryRequest(BaseModel):
    symbol: str
    custom_capital: Optional[float] = None


class TradeEntryResponse(BaseModel):
    trade_id: int
    fill_price: float
    qty: int
    target_price: float
    sl_price: float
    gtt_id: int
    status: str


class OpenPositionRow(BaseModel):
    id: int
    symbol: str
    segment: Optional[str] = None
    entry_date: datetime
    entry_price: float
    ltp: Optional[float] = None
    pnl_pct: Optional[float] = None
    pnl_inr: Optional[float] = None
    initial_target_price: Optional[float] = None
    pct_to_target: Optional[float] = None
    pct_to_sl: Optional[float] = None
    days_held: Optional[int] = None

    class Config:
        from_attributes = True


class ClosedTradeRow(BaseModel):
    id: int
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime] = None
    entry_price: float
    exit_price: Optional[float] = None
    qty: int
    pnl_inr: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    days_held: Optional[int] = None
    badge_at_entry: Optional[str] = None
    llm_verdict_at_entry: Optional[str] = None
    pullback_score_at_entry: Optional[float] = None
    shubham_score_at_entry: Optional[float] = None

    class Config:
        from_attributes = True


class TradeDetail(BaseModel):
    id: int
    symbol: str
    segment: Optional[str] = None
    entry_date: datetime
    exit_date: Optional[datetime] = None
    entry_price: float
    exit_price: Optional[float] = None
    qty: int
    capital_deployed: float
    initial_target_price: Optional[float] = None
    initial_sl_price: Optional[float] = None
    pnl_inr: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    days_held: Optional[int] = None
    badge_at_entry: Optional[str] = None
    llm_verdict_at_entry: Optional[str] = None
    pullback_score_at_entry: Optional[float] = None
    shubham_score_at_entry: Optional[float] = None
    notes: Optional[str] = None
    ltp_at_entry: Optional[float] = None
    rsi_at_entry: Optional[float] = None
    pct_below_20d_high_at_entry: Optional[float] = None
    pct_below_50d_high_at_entry: Optional[float] = None
    dist_from_20dma_at_entry: Optional[float] = None
    dist_from_50dma_at_entry: Optional[float] = None
    volume_ratio_at_entry: Optional[float] = None
    swing_low_at_entry: Optional[float] = None
    swing_high_at_entry: Optional[float] = None
    pivot_support_at_entry: Optional[float] = None
    pivot_resistance_at_entry: Optional[float] = None
    green_after_red_at_entry: Optional[bool] = None
    ohlcv: List[OhlcvBar] = []

    class Config:
        from_attributes = True
