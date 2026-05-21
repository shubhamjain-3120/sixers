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
    trail_distance_pct: float
    trail_lock_floor_pct: float
    max_concurrent_positions: int
    min_score_threshold: float
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    total_capital_inr: Optional[int] = None
    nifty50_alloc_pct: Optional[float] = None
    target_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    time_stop_days: Optional[int] = None
    trail_distance_pct: Optional[float] = None
    trail_lock_floor_pct: Optional[float] = None
    max_concurrent_positions: Optional[int] = None
    min_score_threshold: Optional[float] = None
