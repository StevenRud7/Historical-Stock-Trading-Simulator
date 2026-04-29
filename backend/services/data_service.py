# import yfinance as yf
# import pandas as pd
# from datetime import datetime, timedelta
# from typing import List, Optional, Dict
# from sqlalchemy.orm import Session
# from db.database import PriceCache
# import logging

# logger = logging.getLogger(__name__)


# def _date_str(d) -> str:
#     if isinstance(d, str):
#         return d
#     return d.strftime("%Y-%m-%d")


# def fetch_and_cache(ticker: str, start: str, end: str, db: Session) -> bool:
#     """Fetch OHLCV from yfinance, cache in DB. Returns True on success."""
#     try:
#         ticker = ticker.upper().strip()
#         # Add buffer day for yfinance end-date exclusion
#         end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
#         end_buf = end_dt.strftime("%Y-%m-%d")

#         df = yf.download(ticker, start=start, end=end_buf, progress=False, auto_adjust=True)
#         if df.empty:
#             logger.warning(f"No data returned for {ticker}")
#             return False

#         # Flatten MultiIndex columns if present
#         if isinstance(df.columns, pd.MultiIndex):
#             df.columns = df.columns.get_level_values(0)

#         df = df.reset_index()
#         df.columns = [c.lower() for c in df.columns]

#         for _, row in df.iterrows():
#             date_str = _date_str(row["date"])
#             existing = db.query(PriceCache).filter_by(ticker=ticker, date=date_str).first()
#             if existing:
#                 continue
#             bar = PriceCache(
#                 ticker=ticker,
#                 date=date_str,
#                 open=float(row.get("open", 0)),
#                 high=float(row.get("high", 0)),
#                 low=float(row.get("low", 0)),
#                 close=float(row.get("close", 0)),
#                 volume=float(row.get("volume", 0)),
#             )
#             db.add(bar)
#         db.commit()
#         return True
#     except Exception as e:
#         logger.error(f"fetch_and_cache error for {ticker}: {e}")
#         db.rollback()
#         return False


# def get_trading_days(start: str, end: str, db: Session, reference_ticker: str = "SPY") -> List[str]:
#     """Return sorted list of valid trading days between start and end (inclusive)."""
#     # Try to get from cache first using SPY as reference
#     cached = (
#         db.query(PriceCache.date)
#         .filter(
#             PriceCache.ticker == reference_ticker,
#             PriceCache.date >= start,
#             PriceCache.date <= end,
#         )
#         .order_by(PriceCache.date)
#         .all()
#     )
#     if cached:
#         return [r.date for r in cached]

#     # Fetch SPY to get trading days
#     fetch_and_cache(reference_ticker, start, end, db)
#     cached = (
#         db.query(PriceCache.date)
#         .filter(
#             PriceCache.ticker == reference_ticker,
#             PriceCache.date >= start,
#             PriceCache.date <= end,
#         )
#         .order_by(PriceCache.date)
#         .all()
#     )
#     return [r.date for r in cached]


# def get_price_bar(ticker: str, date: str, db: Session) -> Optional[Dict]:
#     """Get single OHLCV bar for ticker on date."""
#     ticker = ticker.upper()
#     bar = db.query(PriceCache).filter_by(ticker=ticker, date=date).first()
#     if bar:
#         return {"date": bar.date, "open": bar.open, "high": bar.high,
#                 "low": bar.low, "close": bar.close, "volume": bar.volume}
#     return None


# def get_close_price(ticker: str, date: str, db: Session) -> Optional[float]:
#     """Get closing price for ticker on date. Falls back to nearest prior date if exact not found."""
#     bar = get_price_bar(ticker, date, db)
#     if bar:
#         return bar["close"]
#     # Fallback: most recent price before this date
#     row = (
#         db.query(PriceCache)
#         .filter(PriceCache.ticker == ticker.upper(), PriceCache.date <= date)
#         .order_by(PriceCache.date.desc())
#         .first()
#     )
#     return row.close if row else None


# def get_chart_data(ticker: str, from_date: str, to_date: str, db: Session) -> List[Dict]:
#     """Get all OHLCV bars for ticker between from_date and to_date."""
#     ticker = ticker.upper()
#     # Ensure data is cached
#     existing_count = (
#         db.query(PriceCache)
#         .filter(PriceCache.ticker == ticker, PriceCache.date >= from_date, PriceCache.date <= to_date)
#         .count()
#     )
#     if existing_count == 0:
#         fetch_and_cache(ticker, from_date, to_date, db)

#     bars = (
#         db.query(PriceCache)
#         .filter(PriceCache.ticker == ticker, PriceCache.date >= from_date, PriceCache.date <= to_date)
#         .order_by(PriceCache.date)
#         .all()
#     )
#     return [{"date": b.date, "open": b.open, "high": b.high,
#              "low": b.low, "close": b.close, "volume": b.volume} for b in bars]


# def ensure_ticker_data(ticker: str, start: str, end: str, db: Session) -> bool:
#     """Make sure ticker data is cached for the full game range."""
#     ticker = ticker.upper()
#     count = db.query(PriceCache).filter(
#         PriceCache.ticker == ticker,
#         PriceCache.date >= start,
#         PriceCache.date <= end
#     ).count()
#     if count > 0:
#         return True
#     return fetch_and_cache(ticker, start, end, db)


# def validate_ticker(ticker: str) -> bool:
#     """Check if a ticker is valid by attempting a small fetch."""
#     try:
#         ticker = ticker.upper().strip()
#         info = yf.Ticker(ticker).fast_info
#         return hasattr(info, 'last_price') and info.last_price is not None
#     except Exception:
#         return False


# # Popular tickers for autocomplete
# POPULAR_TICKERS = [
#     {"symbol": "AAPL", "name": "Apple Inc."},
#     {"symbol": "MSFT", "name": "Microsoft Corp."},
#     {"symbol": "GOOGL", "name": "Alphabet Inc."},
#     {"symbol": "AMZN", "name": "Amazon.com Inc."},
#     {"symbol": "TSLA", "name": "Tesla Inc."},
#     {"symbol": "NVDA", "name": "NVIDIA Corp."},
#     {"symbol": "META", "name": "Meta Platforms"},
#     {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
#     {"symbol": "JPM", "name": "JPMorgan Chase"},
#     {"symbol": "V", "name": "Visa Inc."},
#     {"symbol": "JNJ", "name": "Johnson & Johnson"},
#     {"symbol": "WMT", "name": "Walmart Inc."},
#     {"symbol": "PG", "name": "Procter & Gamble"},
#     {"symbol": "MA", "name": "Mastercard Inc."},
#     {"symbol": "UNH", "name": "UnitedHealth Group"},
#     {"symbol": "HD", "name": "Home Depot"},
#     {"symbol": "DIS", "name": "Walt Disney Co."},
#     {"symbol": "BAC", "name": "Bank of America"},
#     {"symbol": "NFLX", "name": "Netflix Inc."},
#     {"symbol": "ADBE", "name": "Adobe Inc."},
#     {"symbol": "CRM", "name": "Salesforce Inc."},
#     {"symbol": "AMD", "name": "Advanced Micro Devices"},
#     {"symbol": "INTC", "name": "Intel Corp."},
#     {"symbol": "PYPL", "name": "PayPal Holdings"},
#     {"symbol": "SPOT", "name": "Spotify Technology"},
#     {"symbol": "UBER", "name": "Uber Technologies"},
#     {"symbol": "LYFT", "name": "Lyft Inc."},
#     {"symbol": "SNAP", "name": "Snap Inc."},
#     {"symbol": "TWTR", "name": "Twitter Inc."},
#     {"symbol": "COIN", "name": "Coinbase Global"},
#     {"symbol": "SQ", "name": "Block Inc."},
#     {"symbol": "SHOP", "name": "Shopify Inc."},
#     {"symbol": "ZM", "name": "Zoom Video"},
#     {"symbol": "PLTR", "name": "Palantir Technologies"},
#     {"symbol": "SPY", "name": "S&P 500 ETF"},
#     {"symbol": "QQQ", "name": "Nasdaq 100 ETF"},
#     {"symbol": "GLD", "name": "Gold ETF"},
#     {"symbol": "XOM", "name": "Exxon Mobil"},
#     {"symbol": "CVX", "name": "Chevron Corp."},
#     {"symbol": "PFE", "name": "Pfizer Inc."},
#     {"symbol": "MRNA", "name": "Moderna Inc."},
#     {"symbol": "BA", "name": "Boeing Co."},
#     {"symbol": "GE", "name": "General Electric"},
#     {"symbol": "F", "name": "Ford Motor Co."},
#     {"symbol": "GM", "name": "General Motors"},
#     {"symbol": "RIVN", "name": "Rivian Automotive"},
# ]

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from db.database import PriceCache
import logging

logger = logging.getLogger(__name__)


def _date_str(d) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")


def fetch_and_cache(ticker: str, start: str, end: str, db: Session) -> bool:
    """Fetch OHLCV from yfinance, cache in DB. Returns True on success."""
    try:
        ticker = ticker.upper().strip()
        # Add buffer day for yfinance end-date exclusion
        end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        end_buf = end_dt.strftime("%Y-%m-%d")

        df = yf.download(ticker, start=start, end=end_buf, progress=False, auto_adjust=True)
        if df.empty:
            logger.warning(f"No data returned for {ticker}")
            return False

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]

        for _, row in df.iterrows():
            date_str = _date_str(row["date"])
            existing = db.query(PriceCache).filter_by(ticker=ticker, date=date_str).first()
            if existing:
                continue
            bar = PriceCache(
                ticker=ticker,
                date=date_str,
                open=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                close=float(row.get("close", 0)),
                volume=float(row.get("volume", 0)),
            )
            db.add(bar)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"fetch_and_cache error for {ticker}: {e}")
        db.rollback()
        return False


def _is_nyse_holiday(d: datetime) -> bool:
    """Return True if the date is a NYSE holiday (covers 1990-2035)."""
    y, m, day = d.year, d.month, d.day

    # New Year's Day (and observed)
    if m == 1 and day == 1: return True
    if m == 12 and day == 31 and d.weekday() == 4: return True  # Fri observed
    if m == 1 and day == 2 and d.weekday() == 0: return True    # Mon observed

    # MLK Day — 3rd Monday of January (since 1998)
    if y >= 1998 and m == 1 and d.weekday() == 0:
        if 15 <= day <= 21: return True

    # Presidents Day — 3rd Monday of February
    if m == 2 and d.weekday() == 0:
        if 15 <= day <= 21: return True

    # Good Friday — Easter minus 2 days
    easter = _easter(y)
    good_friday = easter - timedelta(days=2)
    if d.date() == good_friday.date(): return True

    # Memorial Day — last Monday of May
    if m == 5 and d.weekday() == 0 and day >= 25: return True

    # Juneteenth — June 19 (since 2022)
    if y >= 2022 and m == 6 and day == 19: return True
    if y >= 2022 and m == 6 and day == 18 and d.weekday() == 4: return True  # Fri observed
    if y >= 2022 and m == 6 and day == 20 and d.weekday() == 0: return True  # Mon observed

    # Independence Day — July 4
    if m == 7 and day == 4: return True
    if m == 7 and day == 3 and d.weekday() == 4: return True   # Fri observed
    if m == 7 and day == 5 and d.weekday() == 0: return True   # Mon observed

    # Labor Day — 1st Monday of September
    if m == 9 and d.weekday() == 0 and day <= 7: return True

    # Thanksgiving — 4th Thursday of November
    if m == 11 and d.weekday() == 3:
        if 22 <= day <= 28: return True

    # Christmas — December 25
    if m == 12 and day == 25: return True
    if m == 12 and day == 24 and d.weekday() == 4: return True  # Fri observed
    if m == 12 and day == 26 and d.weekday() == 0: return True  # Mon observed

    return False


def _easter(year: int) -> datetime:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime(year, month, day + 1)


def get_trading_days(start: str, end: str, db: Session, reference_ticker: str = "SPY") -> List[str]:
    """Return sorted list of NYSE trading days between start and end (inclusive).
    Uses a pure-Python calendar — no network call, no SPY dependency."""
    # 1. Check cache first — if the user's actual ticker is already cached, use those dates
    any_cached = (
        db.query(PriceCache.date)
        .filter(PriceCache.date >= start, PriceCache.date <= end)
        .order_by(PriceCache.date)
        .limit(1)
        .first()
    )
    if any_cached:
        # Use any ticker already in cache as the day source (avoids re-fetching SPY)
        cached = (
            db.query(PriceCache.date)
            .filter(PriceCache.date >= start, PriceCache.date <= end)
            .order_by(PriceCache.date)
            .distinct()
            .all()
        )
        if cached:
            return [r.date for r in cached]

    # 2. Fall back to pure-Python NYSE calendar computation — zero network calls
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")
    days = []
    cur = start_dt
    while cur <= end_dt:
        # Skip weekends (Mon=0 … Sun=6)
        if cur.weekday() < 5 and not _is_nyse_holiday(cur):
            days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return days



def get_price_bar(ticker: str, date: str, db: Session) -> Optional[Dict]:
    """Get single OHLCV bar for ticker on date."""
    ticker = ticker.upper()
    bar = db.query(PriceCache).filter_by(ticker=ticker, date=date).first()
    if bar:
        return {"date": bar.date, "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close, "volume": bar.volume}
    return None


def get_close_price(ticker: str, date: str, db: Session) -> Optional[float]:
    """Get closing price for ticker on date. Falls back to nearest prior date if exact not found."""
    bar = get_price_bar(ticker, date, db)
    if bar:
        return bar["close"]
    # Fallback: most recent price before this date
    row = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper(), PriceCache.date <= date)
        .order_by(PriceCache.date.desc())
        .first()
    )
    return row.close if row else None


def get_chart_data(ticker: str, from_date: str, to_date: str, db: Session) -> List[Dict]:
    """Get all OHLCV bars for ticker between from_date and to_date."""
    ticker = ticker.upper()
    # Ensure data is cached
    existing_count = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker, PriceCache.date >= from_date, PriceCache.date <= to_date)
        .count()
    )
    if existing_count == 0:
        fetch_and_cache(ticker, from_date, to_date, db)

    bars = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker, PriceCache.date >= from_date, PriceCache.date <= to_date)
        .order_by(PriceCache.date)
        .all()
    )
    return [{"date": b.date, "open": b.open, "high": b.high,
             "low": b.low, "close": b.close, "volume": b.volume} for b in bars]


def ensure_ticker_data(ticker: str, start: str, end: str, db: Session) -> bool:
    """Make sure ticker data is cached for the full game range."""
    ticker = ticker.upper()
    count = db.query(PriceCache).filter(
        PriceCache.ticker == ticker,
        PriceCache.date >= start,
        PriceCache.date <= end
    ).count()
    if count > 0:
        return True
    return fetch_and_cache(ticker, start, end, db)


def validate_ticker(ticker: str) -> bool:
    """Check if a ticker is valid by attempting a small fetch."""
    try:
        ticker = ticker.upper().strip()
        info = yf.Ticker(ticker).fast_info
        return hasattr(info, 'last_price') and info.last_price is not None
    except Exception:
        return False


# Popular tickers for autocomplete
POPULAR_TICKERS = [
    {"symbol": "AAPL", "name": "Apple Inc."},
    {"symbol": "MSFT", "name": "Microsoft Corp."},
    {"symbol": "GOOGL", "name": "Alphabet Inc."},
    {"symbol": "AMZN", "name": "Amazon.com Inc."},
    {"symbol": "TSLA", "name": "Tesla Inc."},
    {"symbol": "NVDA", "name": "NVIDIA Corp."},
    {"symbol": "META", "name": "Meta Platforms"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    {"symbol": "JPM", "name": "JPMorgan Chase"},
    {"symbol": "V", "name": "Visa Inc."},
    {"symbol": "JNJ", "name": "Johnson & Johnson"},
    {"symbol": "WMT", "name": "Walmart Inc."},
    {"symbol": "PG", "name": "Procter & Gamble"},
    {"symbol": "MA", "name": "Mastercard Inc."},
    {"symbol": "UNH", "name": "UnitedHealth Group"},
    {"symbol": "HD", "name": "Home Depot"},
    {"symbol": "DIS", "name": "Walt Disney Co."},
    {"symbol": "BAC", "name": "Bank of America"},
    {"symbol": "NFLX", "name": "Netflix Inc."},
    {"symbol": "ADBE", "name": "Adobe Inc."},
    {"symbol": "CRM", "name": "Salesforce Inc."},
    {"symbol": "AMD", "name": "Advanced Micro Devices"},
    {"symbol": "INTC", "name": "Intel Corp."},
    {"symbol": "PYPL", "name": "PayPal Holdings"},
    {"symbol": "SPOT", "name": "Spotify Technology"},
    {"symbol": "UBER", "name": "Uber Technologies"},
    {"symbol": "LYFT", "name": "Lyft Inc."},
    {"symbol": "SNAP", "name": "Snap Inc."},
    {"symbol": "TWTR", "name": "Twitter Inc."},
    {"symbol": "COIN", "name": "Coinbase Global"},
    {"symbol": "SQ", "name": "Block Inc."},
    {"symbol": "SHOP", "name": "Shopify Inc."},
    {"symbol": "ZM", "name": "Zoom Video"},
    {"symbol": "PLTR", "name": "Palantir Technologies"},
    {"symbol": "SPY", "name": "S&P 500 ETF"},
    {"symbol": "QQQ", "name": "Nasdaq 100 ETF"},
    {"symbol": "GLD", "name": "Gold ETF"},
    {"symbol": "XOM", "name": "Exxon Mobil"},
    {"symbol": "CVX", "name": "Chevron Corp."},
    {"symbol": "PFE", "name": "Pfizer Inc."},
    {"symbol": "MRNA", "name": "Moderna Inc."},
    {"symbol": "BA", "name": "Boeing Co."},
    {"symbol": "GE", "name": "General Electric"},
    {"symbol": "F", "name": "Ford Motor Co."},
    {"symbol": "GM", "name": "General Motors"},
    {"symbol": "RIVN", "name": "Rivian Automotive"},
]