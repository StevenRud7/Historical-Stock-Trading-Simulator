import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from db.database import GameSession, Position, Trade
from services.data_service import get_close_price, ensure_ticker_data
import logging

logger = logging.getLogger(__name__)


def fast_forward(game_id: str, days: int, db: Session) -> Dict[str, Any]:
    """Simulate N trading days forward. Returns a full summary report."""
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

    # Clamp to available days
    max_advance = len(trading_days) - current_idx - 1
    days_to_sim = min(days, max_advance)

    if days_to_sim <= 0:
        raise ValueError("No more trading days to simulate")

    start_date = game.current_date
    start_value = _calc_portfolio_value(game, db)

    # Ensure all held tickers have data fetched
    positions = db.query(Position).filter_by(game_id=game_id).all()
    for pos in positions:
        ensure_ticker_data(pos.ticker, game.start_date, game.end_date, db)

    daily_summaries = []
    prev_value = start_value
    game_over = False
    game_over_date = None

    for i in range(1, days_to_sim + 1):
        sim_date = trading_days[current_idx + i]
        new_value = _calc_portfolio_value_on_date(game, sim_date, db)

        daily_pnl = new_value - prev_value
        daily_pnl_pct = (daily_pnl / prev_value * 100) if prev_value > 0 else 0

        daily_summaries.append({
            "date": sim_date,
            "portfolio_value": round(new_value, 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 2),
        })

        if new_value <= 0:
            game_over = True
            game_over_date = sim_date
            game.current_date = sim_date
            game.status = "game_over"
            db.commit()
            break

        prev_value = new_value

    if not game_over:
        game.current_date = trading_days[current_idx + days_to_sim]
        if current_idx + days_to_sim >= len(trading_days) - 1:
            game.status = "completed"
        db.commit()

    end_value = _calc_portfolio_value(game, db)
    net_pnl = end_value - start_value
    net_pnl_pct = (net_pnl / start_value * 100) if start_value > 0 else 0

    best_day = max(daily_summaries, key=lambda d: d["daily_pnl"]) if daily_summaries else None
    worst_day = min(daily_summaries, key=lambda d: d["daily_pnl"]) if daily_summaries else None

    # Position change summary
    position_changes = _build_position_changes(game, positions, start_date, game.current_date, db)

    msg = None
    if game_over:
        msg = f"💀 Portfolio hit $0 on {game_over_date}. Game over!"
    elif game.status == "completed":
        msg = "🎉 You've reached the end of the simulation!"

    return {
        "game_id": game_id,
        "days_simulated": len(daily_summaries),
        "start_date": start_date,
        "end_date": game.current_date,
        "start_value": round(start_value, 2),
        "end_value": round(end_value, 2),
        "net_pnl": round(net_pnl, 2),
        "net_pnl_pct": round(net_pnl_pct, 2),
        "best_day": best_day,
        "worst_day": worst_day,
        "daily_summaries": daily_summaries,
        "position_changes": position_changes,
        "game_over": game_over,
        "message": msg,
    }


def _calc_portfolio_value(game: GameSession, db: Session) -> float:
    return _calc_portfolio_value_on_date(game, game.current_date, db)


def _calc_portfolio_value_on_date(game: GameSession, date: str, db: Session) -> float:
    positions = db.query(Position).filter_by(game_id=game.id).all()
    total = game.cash_balance

    for pos in positions:
        price = get_close_price(pos.ticker, date, db) or pos.avg_cost
        if pos.position_type == "LONG":
            total += pos.quantity * price
        else:
            pnl = (pos.avg_cost - price) * pos.quantity
            total += pnl

    return max(total, 0)


def _build_position_changes(game: GameSession, positions: List, start_date: str, end_date: str, db: Session) -> List[Dict]:
    changes = []
    for pos in positions:
        start_price = get_close_price(pos.ticker, start_date, db) or pos.avg_cost
        end_price = get_close_price(pos.ticker, end_date, db) or pos.avg_cost
        price_change = end_price - start_price
        price_change_pct = (price_change / start_price * 100) if start_price > 0 else 0

        if pos.position_type == "LONG":
            value_change = price_change * pos.quantity
        else:
            value_change = -price_change * pos.quantity

        changes.append({
            "ticker": pos.ticker,
            "position_type": pos.position_type,
            "quantity": round(pos.quantity, 4),
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "price_change": round(price_change, 2),
            "price_change_pct": round(price_change_pct, 2),
            "value_change": round(value_change, 2),
        })

    return sorted(changes, key=lambda x: abs(x["value_change"]), reverse=True)