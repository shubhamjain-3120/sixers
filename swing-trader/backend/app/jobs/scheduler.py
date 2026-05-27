import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

_scheduler: BackgroundScheduler = None


def _is_trading_day() -> bool:
    from datetime import date
    today = date.today()
    if today.weekday() >= 5:  # Sat=5, Sun=6
        return False
    # Basic NSE holiday check — extend with full calendar if needed
    NSE_HOLIDAYS_2025_2026 = {
        # 2025
        (2025, 2, 26), (2025, 3, 14), (2025, 3, 31), (2025, 4, 10),
        (2025, 4, 14), (2025, 4, 18), (2025, 5, 1), (2025, 8, 15),
        (2025, 8, 27), (2025, 10, 2), (2025, 10, 2), (2025, 10, 24),
        (2025, 11, 5), (2025, 12, 25),
        # 2026
        (2026, 1, 26), (2026, 3, 2), (2026, 3, 20), (2026, 3, 31),
        (2026, 4, 3), (2026, 4, 14), (2026, 5, 1), (2026, 8, 15),
        (2026, 10, 2), (2026, 11, 11), (2026, 12, 25),
    }
    return (today.year, today.month, today.day) not in NSE_HOLIDAYS_2025_2026


def _trading_day_job(fn):
    """Wrapper: only runs fn if today is a trading day."""
    def wrapper(*args, **kwargs):
        if _is_trading_day():
            fn(*args, **kwargs)
        else:
            logger.info(f"Skipping {fn.__name__} — not a trading day")
    wrapper.__name__ = fn.__name__
    return wrapper


# ── Job functions ────────────────────────────────────────────────────────────

def job_universe_refresh():
    from app.nse.universe import refresh_universe
    refresh_universe()


def job_kite_instruments():
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    from app.db.models import Instrument
    db = SessionLocal()
    try:
        kite = get_kite_client(db)
        if not kite:
            return
        all_instruments = kite.instruments("NSE")
        token_map = {i["tradingsymbol"]: i["instrument_token"] for i in all_instruments}
        for inst in db.query(Instrument).all():
            tok = token_map.get(inst.symbol)
            if tok:
                inst.kite_instrument_token = tok
        db.commit()
        logger.info("Kite instrument tokens refreshed")
    finally:
        db.close()


def job_mark_token_expired():
    from app.db.session import SessionLocal
    from app.db.models import KiteToken
    from datetime import datetime
    db = SessionLocal()
    try:
        token = db.query(KiteToken).order_by(KiteToken.created_at.desc()).first()
        if token and token.expires_at <= datetime.utcnow():
            logger.info("Kite token is expired")
    finally:
        db.close()


def job_auto_login():
    from app.db.session import SessionLocal
    from app.kite.auto_login import auto_login
    from app.telegram_bot.reminder import send_alert
    from app.config import settings
    db = SessionLocal()
    try:
        auto_login(db)
    except Exception as e:
        logger.error(f"Auto-login failed: {e}")
        send_alert(
            f"⚠️ Kite auto-login failed: {e}\n\n"
            f"Tap to login manually: {settings.app_base_url}/dashboard"
        )
    finally:
        db.close()


@_trading_day_job
def job_morning_sync():
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    from app.trading.position_cycle import run_cycle
    db = SessionLocal()
    try:
        kite = get_kite_client(db)
        if kite:
            run_cycle(db, kite)
    finally:
        db.close()


@_trading_day_job
def job_revalidate_candidates():
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    from app.scanner.runner import revalidate_candidates
    db = SessionLocal()
    try:
        kite = get_kite_client(db)
        if kite:
            revalidate_candidates(db, kite)
    finally:
        db.close()


@_trading_day_job
def job_position_cycle():
    from app.jobs.runner import run_job
    run_job("position-cycle")


@_trading_day_job
def job_time_stop():
    from app.jobs.runner import run_job
    run_job("time-stop")


@_trading_day_job
def job_daily_scan():
    from app.jobs.runner import run_job
    run_job("scan")


@_trading_day_job
def job_eod_sync():
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    from app.trading.position_cycle import run_cycle
    db = SessionLocal()
    try:
        kite = get_kite_client(db)
        if kite:
            run_cycle(db, kite)
    finally:
        db.close()



@_trading_day_job
def job_news_classification():
    from app.jobs.runner import run_job
    run_job("news-classify")


# ── Scheduler setup ──────────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    global _scheduler
    sched = BackgroundScheduler(timezone=IST)

    # Universe refresh — 1st of every month 01:00 IST
    sched.add_job(job_universe_refresh, CronTrigger(day=1, hour=1, minute=0, timezone=IST), id="universe_refresh")
    # Kite instruments dump — daily 08:30 IST
    sched.add_job(job_kite_instruments, CronTrigger(hour=8, minute=30, timezone=IST), id="kite_instruments")
    # Mark token expired — daily 06:00 IST
    sched.add_job(job_mark_token_expired, CronTrigger(hour=6, minute=0, timezone=IST), id="mark_token_expired")
    # Auto-login — weekdays 06:32 IST (after token-expiry mark, before morning sync)
    sched.add_job(job_auto_login, CronTrigger(day_of_week="mon-fri", hour=6, minute=32, timezone=IST), id="auto_login")
    # Morning sync — 09:00 IST trading days
    sched.add_job(job_morning_sync, CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=IST), id="morning_sync")
    # Candidate re-validation — 09:00 IST trading days
    sched.add_job(job_revalidate_candidates, CronTrigger(day_of_week="mon-fri", hour=9, minute=2, timezone=IST), id="revalidate")
    # Position cycle — every 15 min 09:15–15:30 (three ranges to stay within bounds)
    sched.add_job(job_position_cycle, CronTrigger(day_of_week="mon-fri", hour=9, minute="15,30,45", timezone=IST), id="position_cycle_9")
    sched.add_job(job_position_cycle, CronTrigger(day_of_week="mon-fri", hour="10-14", minute="0,15,30,45", timezone=IST), id="position_cycle_10_14")
    sched.add_job(job_position_cycle, CronTrigger(day_of_week="mon-fri", hour=15, minute="0,15,30", timezone=IST), id="position_cycle_15")
    # Time-stop — 15:00 IST
    sched.add_job(job_time_stop, CronTrigger(day_of_week="mon-fri", hour=15, minute=0, timezone=IST), id="time_stop")
    # Daily scanner — 15:45 IST
    sched.add_job(job_daily_scan, CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=IST), id="daily_scan")
    # EOD sync — 16:00 IST
    sched.add_job(job_eod_sync, CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone=IST), id="eod_sync")
    # News classification — 18:00 IST
    sched.add_job(job_news_classification, CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone=IST), id="news_classification")

    _scheduler = sched
    return sched
