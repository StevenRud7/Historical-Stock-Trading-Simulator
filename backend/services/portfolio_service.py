from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from db.database import GameSession, Position, Trade
from services.data_service import get_close_price, ensure_ticker_data
import logging

logger = logging.getLogger(__name__)


def execute_trade(game_id: str, ticker: str, action: str, quantity: float, db: Session) -> Dict[str, Any]:
    """Execute a trade. Actions: BUY, SELL, SHORT, COVER."""
    ticker = ticker.upper().strip()
    action = action.upper().strip()

    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise ValueError("Game not found")
    if game.status != "active":
        raise ValueError("Game is not active")

    # Get current price
    price = get_close_price(ticker, game.current_date, db)
    if price is None:
        ensure_ticker_data(ticker, game.start_date, game.end_date, db)
        price = get_close_price(ticker, game.current_date, db)
    if price is None:
        raise ValueError(f"No price data available for {ticker} on {game.current_date}. Please verify the ticker is valid and has data in your date range.")

    total_value = round(price * quantity, 2)
    realized_pnl = 0.0
    new_position_qty = 0.0

    if action == "BUY":
        if game.cash_balance < total_value:
            raise ValueError(f"Insufficient funds. Need ${total_value:,.2f}, have ${game.cash_balance:,.2f}")
        game.cash_balance = round(game.cash_balance - total_value, 4)
        pos = _get_or_create_position(game_id, ticker, "LONG", db)
        # Average cost calculation
        old_total = pos.avg_cost * pos.quantity
        pos.quantity = round(pos.quantity + quantity, 4)
        pos.avg_cost = round((old_total + total_value) / pos.quantity, 4) if pos.quantity > 0 else price
        new_position_qty = pos.quantity

    elif action == "SELL":
        pos = db.query(Position).filter_by(game_id=game_id, ticker=ticker, position_type="LONG").first()
        if not pos or pos.quantity < quantity:
            have = pos.quantity if pos else 0
            raise ValueError(f"Insufficient shares. Have {have:.4f}, trying to sell {quantity:.4f}")
        realized_pnl = round((price - pos.avg_cost) * quantity, 2)
        pos.quantity = round(pos.quantity - quantity, 4)
        if pos.quantity <= 0.000001:
            db.delete(pos)
            new_position_qty = 0
        else:
            new_position_qty = pos.quantity
        game.cash_balance = round(game.cash_balance + total_value, 4)

    elif action == "SHORT":
        # Simplified short: requires cash collateral = total value
        if game.cash_balance < total_value:
            raise ValueError(f"Insufficient margin. Need ${total_value:,.2f} collateral, have ${game.cash_balance:,.2f}")
        game.cash_balance = round(game.cash_balance - total_value, 4)
        pos = _get_or_create_position(game_id, ticker, "SHORT", db)
        old_total = pos.avg_cost * pos.quantity
        pos.quantity = round(pos.quantity + quantity, 4)
        pos.avg_cost = round((old_total + total_value) / pos.quantity, 4) if pos.quantity > 0 else price
        new_position_qty = pos.quantity

    elif action == "COVER":
        pos = db.query(Position).filter_by(game_id=game_id, ticker=ticker, position_type="SHORT").first()
        if not pos or pos.quantity < quantity:
            have = pos.quantity if pos else 0
            raise ValueError(f"Insufficient short position. Have {have:.4f} shorted, trying to cover {quantity:.4f}")
        # Return collateral + profit/loss
        collateral_per_share = pos.avg_cost
        realized_pnl = round((pos.avg_cost - price) * quantity, 2)  # profit if price fell
        # Return original collateral
        game.cash_balance = round(game.cash_balance + (collateral_per_share * quantity) + realized_pnl, 4)
        pos.quantity = round(pos.quantity - quantity, 4)
        if pos.quantity <= 0.000001:
            db.delete(pos)
            new_position_qty = 0
        else:
            new_position_qty = pos.quantity
    else:
        raise ValueError(f"Unknown action: {action}. Use BUY, SELL, SHORT, or COVER")

    # Record trade
    trade = Trade(
        game_id=game_id,
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
        total_value=total_value,
        trade_date=game.current_date,
        realized_pnl=realized_pnl,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return {
        "success": True,
        "message": f"✅ {action} {quantity} {ticker} @ ${price:,.2f}",
        "trade_id": trade.id,
        "ticker": ticker,
        "action": action,
        "quantity": quantity,
        "price": price,
        "total_cost": total_value,
        "realized_pnl": realized_pnl,
        "new_cash_balance": round(game.cash_balance, 2),
        "new_position_qty": round(new_position_qty, 4),
    }


def get_portfolio_snapshot(game_id: str, db: Session) -> Dict[str, Any]:
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise ValueError("Game not found")

    positions = db.query(Position).filter_by(game_id=game_id).all()
    position_list = []
    total_positions_value = 0.0
    total_unrealized = 0.0

    for pos in positions:
        price = get_close_price(pos.ticker, game.current_date, db) or pos.avg_cost
        if pos.position_type == "LONG":
            current_value = pos.quantity * price
            unrealized_pnl = (price - pos.avg_cost) * pos.quantity
        else:
            current_value = pos.quantity * pos.avg_cost
            unrealized_pnl = (pos.avg_cost - price) * pos.quantity

        pnl_pct = (unrealized_pnl / (pos.avg_cost * pos.quantity) * 100) if pos.avg_cost * pos.quantity > 0 else 0
        total_positions_value += current_value
        total_unrealized += unrealized_pnl

        position_list.append({
            "ticker": pos.ticker,
            "quantity": round(pos.quantity, 4),
            "avg_cost": round(pos.avg_cost, 4),
            "current_price": round(price, 4),
            "current_value": round(current_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(pnl_pct, 2),
            "position_type": pos.position_type,
        })

    total_realized = _get_total_realized_pnl(game_id, db)
    total_value = game.cash_balance + total_positions_value
    return_pct = ((total_value - game.initial_balance) / game.initial_balance * 100) if game.initial_balance > 0 else 0

    return {
        "game_id": game_id,
        "as_of_date": game.current_date,
        "cash_balance": round(game.cash_balance, 2),
        "positions": position_list,
        "total_positions_value": round(total_positions_value, 2),
        "total_portfolio_value": round(total_value, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_realized_pnl": round(total_realized, 2),
        "total_return_pct": round(return_pct, 2),
    }


def get_trade_history(game_id: str, db: Session) -> List[Dict]:
    trades = db.query(Trade).filter_by(game_id=game_id).order_by(Trade.id.desc()).all()
    return [
        {
            "id": t.id,
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": t.price,
            "total_value": t.total_value,
            "trade_date": t.trade_date,
            "realized_pnl": t.realized_pnl,
        }
        for t in trades
    ]


def get_end_game_summary(game_id: str, db: Session) -> Dict[str, Any]:
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise ValueError("Game not found")

    from services.game_engine import _get_total_portfolio_value
    final_value = _get_total_portfolio_value(game, db)
    trades = db.query(Trade).filter_by(game_id=game_id).all()

    # Open positions at end - included in final_value already
    open_positions_raw = db.query(Position).filter_by(game_id=game_id).all()
    open_positions = []
    total_open_value = 0.0
    total_unrealized = 0.0

    for pos in open_positions_raw:
        price = get_close_price(pos.ticker, game.current_date, db) or pos.avg_cost
        if pos.position_type == "LONG":
            current_value  = pos.quantity * price
            unrealized_pnl = (price - pos.avg_cost) * pos.quantity
        else:
            current_value  = pos.quantity * pos.avg_cost
            unrealized_pnl = (pos.avg_cost - price) * pos.quantity
        pnl_pct = (unrealized_pnl / (pos.avg_cost * pos.quantity) * 100) if pos.avg_cost * pos.quantity > 0 else 0
        total_open_value += current_value
        total_unrealized += unrealized_pnl
        open_positions.append({
            "ticker":             pos.ticker,
            "position_type":      pos.position_type,
            "quantity":           round(pos.quantity, 4),
            "avg_cost":           round(pos.avg_cost, 2),
            "current_price":      round(price, 2),
            "current_value":      round(current_value, 2),
            "unrealized_pnl":     round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(pnl_pct, 2),
        })

    total_realized = _get_total_realized_pnl(game_id, db)
    total_return = final_value - game.initial_balance
    return_pct   = (total_return / game.initial_balance * 100) if game.initial_balance > 0 else 0

    winning        = [t for t in trades if t.realized_pnl > 0]
    losing         = [t for t in trades if t.realized_pnl < 0]
    closing_trades = [t for t in trades if t.action in ("SELL", "COVER")]

    best_trade  = max(closing_trades, key=lambda t: t.realized_pnl, default=None)
    worst_trade = min(closing_trades, key=lambda t: t.realized_pnl, default=None)

    from collections import Counter
    most_traded = Counter(t.ticker for t in trades).most_common(1)[0][0] if trades else None
    win_rate = (len(winning) / len(closing_trades) * 100) if closing_trades else 0

    if   return_pct >= 50:  grade = "S"
    elif return_pct >= 25:  grade = "A"
    elif return_pct >= 10:  grade = "B"
    elif return_pct >= 0:   grade = "C"
    elif return_pct >= -10: grade = "D"
    else:                   grade = "F"

    history = [{"id": t.id, "ticker": t.ticker, "action": t.action,
                "quantity": t.quantity, "price": t.price, "total_value": t.total_value,
                "trade_date": t.trade_date, "realized_pnl": t.realized_pnl}
               for t in sorted(trades, key=lambda x: x.id)]

    return {
        "game_id":              game_id,
        "start_date":           game.start_date,
        "end_date":             game.end_date,
        "initial_balance":      game.initial_balance,
        "final_value":          round(final_value, 2),
        "cash_balance":         round(game.cash_balance, 2),
        "open_positions_value": round(total_open_value, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_realized_pnl":   round(total_realized, 2),
        "total_return":         round(total_return, 2),
        "total_return_pct":     round(return_pct, 2),
        "total_trades":         len(trades),
        "winning_trades":       len(winning),
        "losing_trades":        len(losing),
        "win_rate":             round(win_rate, 1),
        "best_trade":  {"ticker": best_trade.ticker, "action": best_trade.action,
                        "quantity": best_trade.quantity, "price": best_trade.price,
                        "pnl": best_trade.realized_pnl, "date": best_trade.trade_date} if best_trade else None,
        "worst_trade": {"ticker": worst_trade.ticker, "action": worst_trade.action,
                        "quantity": worst_trade.quantity, "price": worst_trade.price,
                        "pnl": worst_trade.realized_pnl, "date": worst_trade.trade_date} if worst_trade else None,
        "most_traded_ticker":   most_traded,
        "open_positions":       open_positions,
        "trade_history":        history,
        "performance_grade":    grade,
    }

def _get_or_create_position(game_id: str, ticker: str, position_type: str, db: Session) -> Position:
    pos = db.query(Position).filter_by(game_id=game_id, ticker=ticker, position_type=position_type).first()
    if not pos:
        game = db.query(GameSession).filter_by(id=game_id).first()
        pos = Position(
            game_id=game_id,
            ticker=ticker,
            quantity=0.0,
            avg_cost=0.0,
            position_type=position_type,
            opened_at=game.current_date if game else "",
        )
        db.add(pos)
        db.flush()
    return pos


def _get_total_realized_pnl(game_id: str, db: Session) -> float:
    trades = db.query(Trade).filter_by(game_id=game_id).all()
    return round(sum(t.realized_pnl or 0 for t in trades), 2)