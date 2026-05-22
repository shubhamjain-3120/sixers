from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import Trade, Config
from app.schemas.stats import StatsSummary, ExitReasonBreakdown, VerdictStats, EquityPoint
from typing import List
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
def get_summary(db: Session = Depends(get_db)):
    cfg = db.query(Config).filter(Config.id == 1).first()
    total_capital = cfg.total_capital_inr if cfg else 0

    open_trades = db.query(Trade).filter(Trade.status == "OPEN").all()
    capital_deployed = sum(t.capital_deployed for t in open_trades)
    capital_available = max(0, total_capital - capital_deployed)

    closed_trades = db.query(Trade).filter(Trade.status == "CLOSED").all()
    total_closed = len(closed_trades)

    today = datetime.utcnow().date()
    todays_pnl = sum(
        t.pnl_inr or 0
        for t in closed_trades
        if t.exit_date and t.exit_date.date() == today
    )

    wins = [t for t in closed_trades if (t.pnl_pct or 0) > 0]
    losses = [t for t in closed_trades if (t.pnl_pct or 0) <= 0]
    win_rate = len(wins) / total_closed if total_closed > 0 else 0.0
    avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    by_reason = ExitReasonBreakdown()
    for t in closed_trades:
        reason = t.exit_reason or ""
        if reason == "target":
            by_reason.target += 1
        elif reason == "trailing_stop":
            by_reason.trailing_stop += 1
        elif reason == "stop_loss":
            by_reason.stop_loss += 1
        elif reason == "time_stop":
            by_reason.time_stop += 1
        elif reason == "manual":
            by_reason.manual += 1

    verdict_map: dict = {}
    for t in closed_trades:
        v = t.llm_verdict_at_entry or "UNKNOWN"
        if v not in verdict_map:
            verdict_map[v] = {"trades": 0, "wins": 0}
        verdict_map[v]["trades"] += 1
        if (t.pnl_pct or 0) > 0:
            verdict_map[v]["wins"] += 1
    by_verdict = {
        v: VerdictStats(
            trades=d["trades"],
            win_rate=d["wins"] / d["trades"] if d["trades"] > 0 else 0.0
        )
        for v, d in verdict_map.items()
    }

    return StatsSummary(
        open_positions=len(open_trades),
        capital_deployed=capital_deployed,
        capital_available=capital_available,
        todays_pnl=todays_pnl,
        total_closed_trades=total_closed,
        win_rate=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        expectancy_pct=expectancy,
        by_exit_reason=by_reason,
        by_llm_verdict=by_verdict,
    )


@router.get("/equity-curve", response_model=List[EquityPoint])
def get_equity_curve(days: int = Query(90, ge=1, le=365), db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    start = today - timedelta(days=days)
    closed = (
        db.query(Trade)
        .filter(Trade.status == "CLOSED", Trade.exit_date >= start)
        .all()
    )
    daily = {}
    for t in closed:
        d = t.exit_date.date()
        daily[d] = daily.get(d, 0) + (t.pnl_inr or 0)

    result = []
    cumulative = 0.0
    for d in sorted(daily):
        cumulative += daily[d]
        result.append(EquityPoint(date=d, equity_inr=cumulative))
    return result
