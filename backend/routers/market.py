from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.database import get_db
from services.data_service import (
    get_chart_data, get_close_price, ensure_ticker_data,
    get_trading_days, POPULAR_TICKERS
)
from db.database import GameSession, PriceCache

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/chart")
def get_chart(
    game_id: str,
    ticker: str,
    db: Session = Depends(get_db)
):
    """Get OHLCV chart data for ticker up to current game date."""
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    ticker = ticker.upper().strip()
    ensure_ticker_data(ticker, game.start_date, game.end_date, db)

    bars = get_chart_data(ticker, game.start_date, game.current_date, db)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No chart data for {ticker} in this date range")

    current_price = bars[-1]["close"] if bars else 0
    prev_price = bars[-2]["close"] if len(bars) > 1 else current_price
    price_change = current_price - prev_price
    price_change_pct = (price_change / prev_price * 100) if prev_price > 0 else 0

    return {
        "ticker": ticker,
        "bars": bars,
        "current_price": round(current_price, 4),
        "price_change": round(price_change, 4),
        "price_change_pct": round(price_change_pct, 2),
    }


@router.get("/price")
def get_price(game_id: str, ticker: str, db: Session = Depends(get_db)):
    """Get current day price for a ticker."""
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    ticker = ticker.upper().strip()
    ensure_ticker_data(ticker, game.start_date, game.end_date, db)
    price = get_close_price(ticker, game.current_date, db)
    if price is None:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker} on {game.current_date}")

    return {"ticker": ticker, "date": game.current_date, "price": price}


@router.get("/validate")
def validate_ticker_endpoint(ticker: str, db: Session = Depends(get_db)):
    """Check if a ticker symbol exists and has data."""
    ticker = ticker.upper().strip()
    # Check cache first
    count = db.query(PriceCache).filter(PriceCache.ticker == ticker).count()
    if count > 0:
        return {"valid": True, "ticker": ticker}
    # Try to fetch a small sample
    from services.data_service import fetch_and_cache
    ok = fetch_and_cache(ticker, "2022-01-03", "2022-01-10", db)
    return {"valid": ok, "ticker": ticker}


@router.get("/search")
def search_tickers(q: str = Query(default="", min_length=0)):
    """Search popular tickers by symbol or name."""
    q = q.upper().strip()
    if not q:
        return {"results": POPULAR_TICKERS[:20]}
    results = [
        t for t in POPULAR_TICKERS
        if q in t["symbol"].upper() or q in t["name"].upper()
    ]
    return {"results": results[:10]}


@router.post("/prefetch")
def prefetch_ticker(game_id: str, ticker: str, db: Session = Depends(get_db)):
    """Pre-fetch ticker data for the game's date range."""
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    ticker = ticker.upper().strip()
    success = ensure_ticker_data(ticker, game.start_date, game.end_date, db)
    price = get_close_price(ticker, game.current_date, db)
    if not success or price is None:
        raise HTTPException(status_code=400, detail=f"Could not fetch data for {ticker}. Please check the ticker symbol.")
    return {"success": True, "ticker": ticker, "current_price": price}


@router.get("/summary-charts")
def get_summary_charts(game_id: str, db: Session = Depends(get_db)):
    """Get full chart data + trade annotations for all tickers traded in a game."""
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    from db.database import Trade, Position
    from collections import defaultdict, Counter

    trades = db.query(Trade).filter_by(game_id=game_id).order_by(Trade.id).all()
    if not trades:
        return {"tickers": [], "charts": {}}

    # All unique tickers traded or still held
    traded_tickers = list({t.ticker for t in trades})
    open_positions = db.query(Position).filter_by(game_id=game_id).all()
    held_tickers = [p.ticker for p in open_positions]
    all_tickers = list({*traded_tickers, *held_tickers})

    # Most interacted ticker: by trade count + total volume
    ticker_score = Counter()
    ticker_volume = defaultdict(float)
    for t in trades:
        ticker_score[t.ticker] += 1
        ticker_volume[t.ticker] += t.total_value
    # Weighted score: count + normalized volume contribution
    fav = max(all_tickers, key=lambda tk: ticker_score[tk] * 2 + (ticker_volume[tk] / max(ticker_volume.values(), default=1)))

    charts = {}
    for ticker in all_tickers:
        ensure_ticker_data(ticker, game.start_date, game.end_date, db)
        bars = get_chart_data(ticker, game.start_date, game.end_date, db)
        ticker_trades = [
            {"date": t.trade_date, "action": t.action,
             "quantity": t.quantity, "price": t.price, "total_value": t.total_value,
             "realized_pnl": t.realized_pnl}
            for t in trades if t.ticker == ticker
        ]
        charts[ticker] = {
            "bars": bars,
            "trades": ticker_trades,
        }

    return {
        "tickers": all_tickers,
        "favourite_ticker": fav,
        "charts": charts,
    }