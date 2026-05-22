"""Single dispatcher for jobs that are triggered both by the scheduler and by
/api/system/* manual-trigger routes. Adding a new background job means adding
one entry to JOBS — no duplication between routes and scheduler.
"""
import logging
import threading

logger = logging.getLogger(__name__)


def _with_db_and_kite(fn):
    def wrapped():
        from app.db.session import SessionLocal
        from app.kite.client import get_kite_client
        db = SessionLocal()
        try:
            kite = get_kite_client(db)
            if kite:
                fn(db, kite)
            else:
                logger.info(f"Skipping {fn.__name__}: no Kite client")
        finally:
            db.close()
    wrapped.__name__ = fn.__name__
    return wrapped


def _scan():
    from app.scanner.runner import run_daily_scan
    run_daily_scan()


def _position_cycle():
    from app.trading.position_cycle import run_cycle
    _with_db_and_kite(run_cycle)()


def _time_stop():
    from app.trading.time_stop import run_time_stop
    _with_db_and_kite(run_time_stop)()


def _news_classify():
    from app.news.classifier import run_news_classification
    run_news_classification()


JOBS = {
    "scan": _scan,
    "position-cycle": _position_cycle,
    "time-stop": _time_stop,
    "news-classify": _news_classify,
}


def run_job(name: str) -> bool:
    """Run the named job synchronously. Returns False if name unknown."""
    fn = JOBS.get(name)
    if not fn:
        return False
    fn()
    return True


def run_job_async(name: str) -> bool:
    """Spawn a daemon thread to run the named job. Returns False if name unknown."""
    fn = JOBS.get(name)
    if not fn:
        return False
    threading.Thread(target=fn, daemon=True).start()
    return True
