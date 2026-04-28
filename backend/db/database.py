from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use /tmp for Render's ephemeral filesystem, or local for dev
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "..", "game_data.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class GameSession(Base):
    __tablename__ = "game_sessions"
    id = Column(String, primary_key=True)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    current_date = Column(String, nullable=False)
    initial_balance = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    status = Column(String, default="active")  # active, won, game_over
    created_at = Column(DateTime, default=datetime.utcnow)
    trading_days_json = Column(Text, default="[]")  # JSON list of valid trading days


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    position_type = Column(String, default="LONG")  # LONG or SHORT
    opened_at = Column(String, nullable=False)
    metadata_json = Column(Text, default="{}")  # reserved for V2 options


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # BUY, SELL, SHORT, COVER
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)
    trade_date = Column(String, nullable=False)
    realized_pnl = Column(Float, default=0.0)
    metadata_json = Column(Text, default="{}")  # reserved for V2


class PriceCache(Base):
    __tablename__ = "price_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    date = Column(String, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    __table_args__ = (
        Index("ix_price_cache_ticker_date", "ticker", "date", unique=True),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")