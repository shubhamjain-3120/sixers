from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

_is_postgres = settings.database_url.startswith("postgresql")

_engine_kwargs = {}
if _is_postgres:
    _engine_kwargs = {"pool_size": 5, "max_overflow": 2, "pool_pre_ping": True}
else:
    _engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Add columns that were added after initial schema creation."""
    new_columns = [
        ("config", "telegram_bot_token", "TEXT", "''"),
        ("config", "telegram_chat_id", "TEXT", "''"),
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
