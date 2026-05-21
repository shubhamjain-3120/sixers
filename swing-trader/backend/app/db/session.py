from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
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
        ("config", "telegram_bot_token", "TEXT DEFAULT ''"),
        ("config", "telegram_chat_id", "TEXT DEFAULT ''"),
    ]
    with engine.connect() as conn:
        for table, col, col_def in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists
