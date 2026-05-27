from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    total_capital_inr = Column(Integer, default=0)
    nifty50_alloc_pct = Column(Float, default=15.0)
    target_pct = Column(Float, default=2.0)
    stop_loss_pct = Column(Float, default=4.0)
    time_stop_days = Column(Integer, default=15)
    trail_distance_pct = Column(Float, default=1.0)
    trail_lock_floor_pct = Column(Float, default=0.5)
    max_concurrent_positions = Column(Integer, default=8)
    min_score_threshold = Column(Float, default=60.0)
    min_shubham_score_threshold = Column(Float, default=60.0)
    telegram_bot_token = Column(String, default="")
    telegram_chat_id = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KiteToken(Base):
    __tablename__ = "kite_tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False)
    public_token = Column(String)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Instrument(Base):
    __tablename__ = "instruments"
    symbol = Column(String, primary_key=True)
    name = Column(String)
    segment = Column(String, nullable=False)
    kite_instrument_token = Column(Integer, nullable=False, default=0)
    sector = Column(String)
    last_refreshed_at = Column(DateTime)


class Blacklist(Base):
    __tablename__ = "blacklist"
    symbol = Column(String, primary_key=True)
    reason = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)


class OhlcvDaily(Base):
    __tablename__ = "ohlcv_daily"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    __table_args__ = (UniqueConstraint("symbol", "date"),)


class DailyScan(Base):
    __tablename__ = "daily_scans"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    scan_date = Column(Date, nullable=False)
    ltp = Column(Float)
    prev_close = Column(Float)
    rsi_14 = Column(Float)
    pct_below_20d_high = Column(Float)
    pct_below_50d_high = Column(Float)
    dist_from_20dma_pct = Column(Float)
    dist_from_50dma_pct = Column(Float)
    volume_ratio = Column(Float)
    swing_low_30d = Column(Float)
    swing_high_30d = Column(Float)
    pivot_support = Column(Float)
    pivot_resistance = Column(Float)
    green_after_red = Column(Boolean, default=False)
    score = Column(Float, nullable=False)
    shubham_score = Column(Float)
    __table_args__ = (UniqueConstraint("symbol", "scan_date"),)



class NewsClassification(Base):
    __tablename__ = "news_classifications"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    classification_date = Column(Date, nullable=False)
    headlines_json = Column(Text)
    per_headline_json = Column(Text)
    verdict = Column(String, nullable=False)
    confidence = Column(Float)
    summary = Column(String)
    raw_response = Column(Text)
    __table_args__ = (UniqueConstraint("symbol", "classification_date"),)


class SetupClassification(Base):
    __tablename__ = "setup_classifications"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    scan_date = Column(Date, nullable=False)
    sector_flag = Column(Boolean, default=False)
    news_verdict = Column(String)
    badge = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("symbol", "scan_date"),)


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    segment = Column(String)
    badge_at_entry = Column(String)
    llm_verdict_at_entry = Column(String)
    pullback_score_at_entry = Column(Float)
    shubham_score_at_entry = Column(Float)
    ltp_at_entry = Column(Float)
    rsi_at_entry = Column(Float)
    pct_below_20d_high_at_entry = Column(Float)
    pct_below_50d_high_at_entry = Column(Float)
    dist_from_20dma_at_entry = Column(Float)
    dist_from_50dma_at_entry = Column(Float)
    volume_ratio_at_entry = Column(Float)
    swing_low_at_entry = Column(Float)
    swing_high_at_entry = Column(Float)
    pivot_support_at_entry = Column(Float)
    pivot_resistance_at_entry = Column(Float)
    green_after_red_at_entry = Column(Boolean)
    entry_date = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    qty = Column(Integer, nullable=False)
    capital_deployed = Column(Float, nullable=False)
    initial_target_price = Column(Float)
    initial_sl_price = Column(Float)
    active_gtt_id = Column(Integer)
    gtt_tag = Column(String, unique=True)
    trailing_state = Column(String, default="initial")
    high_water_mark = Column(Float)
    current_sl_price = Column(Float)
    status = Column(String, default="OPEN")
    exit_date = Column(DateTime)
    exit_price = Column(Float)
    exit_reason = Column(String)
    pnl_inr = Column(Float)
    pnl_pct = Column(Float)
    days_held = Column(Integer)
    notes = Column(Text)


class OrderLog(Base):
    __tablename__ = "order_log"
    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trades.id"))
    kite_order_id = Column(String)
    kite_gtt_id = Column(Integer)
    action = Column(String)
    status = Column(String)
    placed_at = Column(DateTime, default=datetime.utcnow)
    raw_response = Column(Text)
