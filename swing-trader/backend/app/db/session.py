from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

_is_postgres = settings.database_url.startswith("postgresql")

_engine_kwargs = {}
if _is_postgres:
    _engine_kwargs = {"pool_size": 5, "max_overflow": 2, "pool_pre_ping": True}
else:
    _engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(settings.database_url, **_engine_kwargs)

if not _is_postgres:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Add columns and indexes that were added after initial schema creation."""
    new_columns = [
        ("config", "telegram_bot_token", "TEXT", "''"),
        ("config", "telegram_chat_id", "TEXT", "''"),
        ("config", "min_shubham_score_threshold", "REAL", "60.0"),
        ("daily_scans", "shubham_score", "REAL", "NULL"),
        ("trades", "pullback_score_at_entry", "REAL", "NULL"),
        ("trades", "shubham_score_at_entry", "REAL", "NULL"),
        ("trades", "ltp_at_entry", "REAL", "NULL"),
        ("trades", "rsi_at_entry", "REAL", "NULL"),
        ("trades", "pct_below_20d_high_at_entry", "REAL", "NULL"),
        ("trades", "pct_below_50d_high_at_entry", "REAL", "NULL"),
        ("trades", "dist_from_20dma_at_entry", "REAL", "NULL"),
        ("trades", "dist_from_50dma_at_entry", "REAL", "NULL"),
        ("trades", "volume_ratio_at_entry", "REAL", "NULL"),
        ("trades", "swing_low_at_entry", "REAL", "NULL"),
        ("trades", "swing_high_at_entry", "REAL", "NULL"),
        ("trades", "pivot_support_at_entry", "REAL", "NULL"),
        ("trades", "pivot_resistance_at_entry", "REAL", "NULL"),
        ("trades", "green_after_red_at_entry", "INTEGER", "NULL"),
    ]
    indexes = [
        # Covers: filter(scan_date=X, score>=Y).order_by(score DESC)
        "CREATE INDEX IF NOT EXISTS ix_daily_scans_date_score ON daily_scans (scan_date, score DESC)",
        # Covers: filter(scan_date=X).order_by(shubham_score DESC) — default UI sort
        "CREATE INDEX IF NOT EXISTS ix_daily_scans_date_shubham ON daily_scans (scan_date, shubham_score DESC)",
        # Covers: filter(scan_date=X, symbol IN (...))
        "CREATE INDEX IF NOT EXISTS ix_setup_classifications_date ON setup_classifications (scan_date)",
        "CREATE INDEX IF NOT EXISTS ix_news_classifications_date ON news_classifications (classification_date)",
    ]
    with engine.connect() as conn:
        for table, col, col_type, default in new_columns:
            try:
                if _is_postgres:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type} DEFAULT {default}"
                    ))
                else:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default}"
                    ))
                conn.commit()
            except Exception:
                pass  # column already exists (SQLite path)

        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
            except Exception:
                pass

    _backfill_shubham_scores()


def _backfill_shubham_scores():
    """One-time: compute shubham_score for rows where it's NULL."""
    from app.scanner.signals import SignalsBundle
    from app.scanner.scorer import compute_shubham_score

    db = SessionLocal()
    try:
        from app.db.models import DailyScan
        rows = db.query(DailyScan).filter(DailyScan.shubham_score.is_(None)).all()
        if not rows:
            return
        for r in rows:
            sig = SignalsBundle(
                rsi_14=r.rsi_14 or 50.0,
                pct_below_20d_high=r.pct_below_20d_high or 0.0,
                pct_below_50d_high=r.pct_below_50d_high or 0.0,
                dist_from_20dma_pct=r.dist_from_20dma_pct or 0.0,
                dist_from_50dma_pct=r.dist_from_50dma_pct or 0.0,
                volume_ratio=r.volume_ratio or 0.0,
                swing_low_30d=r.swing_low_30d or 0.0,
                swing_high_30d=r.swing_high_30d or 0.0,
                pivot_support=r.pivot_support or 0.0,
                pivot_resistance=r.pivot_resistance or 0.0,
                green_after_red=bool(r.green_after_red),
            )
            r.shubham_score = compute_shubham_score(sig)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
