import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from db.database import GameSession, Position, Trade
from services.data_service import get_trading_days, get_close_price, ensure_ticker_data, fetch_and_cache
import logging

logger = logging.getLogger(__name__)


def create_game(config: dict, db: Session) -> Dict[str, Any]:
    """Create a new game session. Pre-fetches SPY for trading days."""
    game_id = str(uuid.uuid4())[:8]
    start = config["start_date"]
    end = config["end_date"]

    # Fetch SPY to determine valid trading days
    trading_days = get_trading_days(start, end, db)
    if len(trading_days) < 5:
        raise ValueError(f"Date range contains fewer than 5 trading days ({len(trading_days)} found). Please choose a wider range.")

    # Pre-fetch starting tickers
    for ticker in config.get("starting_tickers", ["AAPL"]):
        ensure_ticker_data(ticker.upper(), start, end, db)

    game = GameSession(
        id=game_id,
        start_date=start,
        end_date=end,
        current_date=trading_days[0],
        initial_balance=config["initial_balance"],
        cash_balance=config["initial_balance"],
        status="active",
        trading_days_json=json.dumps(trading_days),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return _game_to_dict(game, db)


def get_game(game_id: str, db: Session) -> Optional[Dict[str, Any]]:
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        return None
    return _game_to_dict(game, db)


def advance_day(game_id: str, db: Session) -> Dict[str, Any]:
    """Advance game by one trading day."""
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise ValueError("Game not found")
    if game.status != "active":
        raise ValueError(f"Game is not active (status: {game.status})")

    trading_days = json.loads(game.trading_days_json)
    try:
        current_idx = trading_days.index(game.current_date)
    except ValueError:
        raise ValueError("Current date not found in trading days")

    if current_idx >= len(trading_days) - 1:
        # Already on last day — mark completed
        game.status = "completed"
        db.commit()
        result = _game_to_dict(game, db, message="🎉 You've reached the end of the simulation!")
        result["portfolio_value_change"] = 0.0
        result["portfolio_value_change_pct"] = 0.0
        result["previous_date"] = game.current_date
        return result

    prev_value = _get_total_portfolio_value(game, db)
    prev_date = game.current_date
    game.current_date = trading_days[current_idx + 1]
    db.commit()

    new_value = _get_total_portfolio_value(game, db)
    change = new_value - prev_value
    change_pct = (change / prev_value * 100) if prev_value > 0 else 0

    # Check game over (bankruptcy)
    if new_value <= 0:
        game.status = "game_over"
        db.commit()
    # Check natural completion — just advanced to the final trading day
    elif trading_days.index(game.current_date) >= len(trading_days) - 1:
        game.status = "completed"
        db.commit()

    result = _game_to_dict(game, db)
    result["previous_date"] = prev_date
    result["portfolio_value_change"] = round(change, 2)
    result["portfolio_value_change_pct"] = round(change_pct, 2)
    if game.status == "completed":
        result["message"] = "\U0001f389 Simulation complete! Viewing your final performance."
    return result


def _get_total_portfolio_value(game: GameSession, db: Session) -> float:
    """Calculate total portfolio value (cash + all positions)."""
    positions = db.query(Position).filter_by(game_id=game.id).all()
    total = game.cash_balance

    for pos in positions:
        price = get_close_price(pos.ticker, game.current_date, db)
        if price is None:
            # Try to fetch missing data
            ensure_ticker_data(pos.ticker, game.start_date, game.end_date, db)
            price = get_close_price(pos.ticker, game.current_date, db)
        if price is None:
            price = pos.avg_cost  # Fallback

        if pos.position_type == "LONG":
            total += pos.quantity * price
        else:  # SHORT: profit when price falls below avg_cost
            pnl = (pos.avg_cost - price) * pos.quantity
            total += pnl  # short collateral is tied up, we track net pnl

    return max(total, 0)


def _get_positions_snapshot(game: GameSession, db: Session) -> List[Dict]:
    positions = db.query(Position).filter_by(game_id=game.id).all()
    result = []
    for pos in positions:
        price = get_close_price(pos.ticker, game.current_date, db) or pos.avg_cost
        if pos.position_type == "LONG":
            current_value = pos.quantity * price
            unrealized_pnl = (price - pos.avg_cost) * pos.quantity
        else:  # SHORT
            current_value = pos.quantity * pos.avg_cost  # collateral
            unrealized_pnl = (pos.avg_cost - price) * pos.quantity

        pnl_pct = (unrealized_pnl / (pos.avg_cost * pos.quantity) * 100) if pos.avg_cost > 0 else 0

        result.append({
            "ticker": pos.ticker,
            "quantity": round(pos.quantity, 4),
            "avg_cost": round(pos.avg_cost, 4),
            "current_price": round(price, 4),
            "current_value": round(current_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(pnl_pct, 2),
            "position_type": pos.position_type,
        })
    return result


def _get_total_realized_pnl(game_id: str, db: Session) -> float:
    trades = db.query(Trade).filter_by(game_id=game_id).all()
    return sum(t.realized_pnl or 0 for t in trades)


def _game_to_dict(game: GameSession, db: Session, message: str = None) -> Dict[str, Any]:
    trading_days = json.loads(game.trading_days_json)
    total_value = _get_total_portfolio_value(game, db)
    positions = _get_positions_snapshot(game, db)

    try:
        current_idx = trading_days.index(game.current_date)
    except ValueError:
        current_idx = 0

    days_remaining = len(trading_days) - current_idx - 1
    return_pct = ((total_value - game.initial_balance) / game.initial_balance * 100) if game.initial_balance > 0 else 0

    return {
        "game_id": game.id,
        "current_date": game.current_date,
        "start_date": game.start_date,
        "end_date": game.end_date,
        "cash_balance": round(game.cash_balance, 2),
        "initial_balance": round(game.initial_balance, 2),
        "total_portfolio_value": round(total_value, 2),
        "total_return_pct": round(return_pct, 2),
        "days_remaining": days_remaining,
        "current_day_index": current_idx,
        "total_trading_days": len(trading_days),
        "status": game.status,
        "positions": positions,
        "message": message,
    }