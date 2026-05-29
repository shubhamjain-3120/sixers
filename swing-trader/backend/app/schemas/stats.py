from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import date


class ExitReasonBreakdown(BaseModel):
    target: int = 0
    stop_loss: int = 0
    time_stop: int = 0
    manual: int = 0


class VerdictStats(BaseModel):
    trades: int = 0
    win_rate: float = 0.0


class StatsSummary(BaseModel):
    open_positions: int
    capital_deployed: float
    capital_available: float
    todays_pnl: float
    this_month_pnl: float = 0.0
    this_fy_pnl: float = 0.0
    total_closed_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    expectancy_pct: float
    by_exit_reason: ExitReasonBreakdown
    by_llm_verdict: Dict[str, VerdictStats]


class EquityPoint(BaseModel):
    date: date
    equity_inr: float
