from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


# ── Game Config ────────────────────────────────────────────────────────────────

class GameConfig(BaseModel):
    start_date: str          # "YYYY-MM-DD"
    end_date: str            # "YYYY-MM-DD"
    initial_balance: float = Field(default=10000.0, ge=1000.0)
    starting_tickers: List[str] = Field(default=["AAPL"])


class GameStateResponse(BaseModel):
    game_id: str
    current_date: str
    start_date: str
    end_date: str
    cash_balance: float
    initial_balance: float
    total_portfolio_value: float
    total_return_pct: float
    days_remaining: int
    current_day_index: int
    total_trading_days: int
    status: str
    positions: List[Dict[str, Any]]
    message: Optional[str] = None


class AdvanceDayResponse(BaseModel):
    game_id: str
    previous_date: str
    new_date: str
    portfolio_value_change: float
    portfolio_value_change_pct: float
    new_cash: float
    new_total_value: float
    days_remaining: int
    status: str
    message: Optional[str] = None


# ── Portfolio / Trade ──────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    game_id: str
    ticker: str
    action: str        # BUY | SELL | SHORT | COVER
    quantity: float = Field(gt=0)


class TradeResponse(BaseModel):
    success: bool
    message: str
    trade_id: Optional[int] = None
    ticker: str
    action: str
    quantity: float
    price: float
    total_cost: float
    realized_pnl: Optional[float] = None
    new_cash_balance: float
    new_position_qty: float


class PositionSnapshot(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    position_type: str


class PortfolioSnapshot(BaseModel):
    game_id: str
    as_of_date: str
    cash_balance: float
    positions: List[PositionSnapshot]
    total_positions_value: float
    total_portfolio_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_return_pct: float


class TradeHistoryItem(BaseModel):
    id: int
    ticker: str
    action: str
    quantity: float
    price: float
    total_value: float
    trade_date: str
    realized_pnl: float


# ── Market Data ────────────────────────────────────────────────────────────────

class PriceBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartDataResponse(BaseModel):
    ticker: str
    bars: List[PriceBar]
    current_price: float
    price_change: float
    price_change_pct: float


# ── Fast Forward ───────────────────────────────────────────────────────────────

class FastForwardRequest(BaseModel):
    game_id: str
    days: int = Field(ge=1, le=365)


class DailySummary(BaseModel):
    date: str
    portfolio_value: float
    daily_pnl: float
    daily_pnl_pct: float


class FastForwardReport(BaseModel):
    game_id: str
    days_simulated: int
    start_date: str
    end_date: str
    start_value: float
    end_value: float
    net_pnl: float
    net_pnl_pct: float
    best_day: Optional[DailySummary]
    worst_day: Optional[DailySummary]
    daily_summaries: List[DailySummary]
    position_changes: List[Dict[str, Any]]
    game_over: bool
    message: Optional[str] = None


# ── End of Game ────────────────────────────────────────────────────────────────

class EndGameSummary(BaseModel):
    game_id: str
    start_date: str
    end_date: str
    initial_balance: float
    final_value: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    best_trade: Optional[Dict[str, Any]]
    worst_trade: Optional[Dict[str, Any]]
    most_traded_ticker: Optional[str]
    trade_history: List[TradeHistoryItem]
    performance_grade: str