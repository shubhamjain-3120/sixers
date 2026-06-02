from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ConfigRead(BaseModel):
    id: int
    total_capital_inr: int
    nifty50_alloc_pct: float
    target_pct: float
    stop_loss_pct: float
    time_stop_days: int
    max_concurrent_positions: int
    min_score_threshold: float
    min_shubham_score_threshold: float
    sl_mode: str = "atr"
    atr_sl_multiplier: float = 2.5
    sl_floor_pct: float = 3.0
    sl_cap_pct: float = 6.0
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    total_capital_inr: Optional[int] = None
    nifty50_alloc_pct: Optional[float] = None
    target_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    time_stop_days: Optional[int] = None
    max_concurrent_positions: Optional[int] = None
    min_score_threshold: Optional[float] = None
    min_shubham_score_threshold: Optional[float] = None
    sl_mode: Optional[str] = None
    atr_sl_multiplier: Optional[float] = None
    sl_floor_pct: Optional[float] = None
    sl_cap_pct: Optional[float] = None
