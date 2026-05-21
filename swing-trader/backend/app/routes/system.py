from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/scan")
def trigger_scan():
    from app.scanner.runner import run_daily_scan
    import threading
    t = threading.Thread(target=run_daily_scan, daemon=True)
    t.start()
    return {"status": "scan_started"}


@router.post("/position-cycle")
def trigger_position_cycle():
    from app.trading.position_cycle import run_cycle
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    import threading

    def _run():
        db = SessionLocal()
        try:
            kite = get_kite_client(db)
            if kite:
                run_cycle(db, kite)
        finally:
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "cycle_started"}


@router.post("/time-stop")
def trigger_time_stop():
    from app.trading.time_stop import run_time_stop
    from app.db.session import SessionLocal
    from app.kite.client import get_kite_client
    import threading

    def _run():
        db = SessionLocal()
        try:
            kite = get_kite_client(db)
            if kite:
                run_time_stop(db, kite)
        finally:
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "time_stop_started"}


@router.post("/news-classify")
def trigger_news_classify():
    from app.news.classifier import run_news_classification
    import threading
    t = threading.Thread(target=run_news_classification, daemon=True)
    t.start()
    return {"status": "classification_started"}


@router.get("/health")
def health():
    return {"status": "ok"}
