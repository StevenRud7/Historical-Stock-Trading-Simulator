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

import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from db.database import PriceCache
import logging

logger = logging.getLogger(__name__)

# ── Shared requests session with browser-like headers ─────────────
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})
_crumb: Optional[str] = None


def _get_crumb() -> Optional[str]:
    """Obtain a Yahoo Finance crumb token (required for v8 API)."""
    global _crumb
    if _crumb:
        return _crumb
    try:
        # Step 1: hit finance.yahoo.com to get session cookies
        _session.get("https://finance.yahoo.com", timeout=10)
        # Step 2: fetch crumb
        r = _session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            timeout=10,
        )
        if r.status_code == 200 and r.text and r.text != "null":
            _crumb = r.text.strip().strip('"')
            logger.info(f"Got Yahoo crumb: {_crumb[:6]}…")
            return _crumb
    except Exception as e:
        logger.warning(f"Could not get crumb: {e}")
    return None


def _fetch_yahoo_direct(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """
    Direct Yahoo Finance v8 API fetch — works on cloud IPs.
    Returns a DataFrame with columns: Date, Open, High, Low, Close, Volume
    or None on failure.
    """
    ticker = ticker.upper()
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
    end_ts   = int(datetime.strptime(end,   "%Y-%m-%d").timestamp()) + 86400

    crumb = _get_crumb()

    for attempt in range(3):
        try:
            params = {
                "interval": "1d",
                "period1": start_ts,
                "period2": end_ts,
                "events": "div,splits",
            }
            if crumb:
                params["crumb"] = crumb

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            r = _session.get(url, params=params, timeout=20)

            if r.status_code == 401 or r.status_code == 403:
                # Crumb expired — reset and retry
                global _crumb
                _crumb = None
                crumb = _get_crumb()
                if crumb:
                    params["crumb"] = crumb
                time.sleep(1.5 * (attempt + 1))
                continue

            if r.status_code != 200:
                logger.warning(f"Yahoo v8 returned {r.status_code} for {ticker}")
                time.sleep(1.5 * (attempt + 1))
                continue

            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                logger.warning(f"No chart result for {ticker}")
                return None

            chart = result[0]
            timestamps = chart.get("timestamp", [])
            indicators  = chart.get("indicators", {})
            quote = indicators.get("quote", [{}])[0]
            adjclose_list = indicators.get("adjclose", [{}])
            adjclose = adjclose_list[0].get("adjclose", []) if adjclose_list else []

            if not timestamps:
                return None

            rows = []
            for i, ts in enumerate(timestamps):
                try:
                    adj = adjclose[i] if adjclose and i < len(adjclose) else None
                    close = adj if adj is not None else quote.get("close", [None])[i]
                    o = quote.get("open",   [None])[i]
                    h = quote.get("high",   [None])[i]
                    l = quote.get("low",    [None])[i]
                    v = quote.get("volume", [None])[i]
                    if close is None or o is None:
                        continue
                    rows.append({
                        "date":   datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
                        "open":   float(o),
                        "high":   float(h) if h else float(o),
                        "low":    float(l) if l else float(o),
                        "close":  float(close),
                        "volume": float(v) if v else 0.0,
                    })
                except (IndexError, TypeError):
                    continue

            if rows:
                return pd.DataFrame(rows)
            return None

        except Exception as e:
            logger.warning(f"_fetch_yahoo_direct attempt {attempt+1} failed for {ticker}: {e}")
            time.sleep(1.5 * (attempt + 1))

    return None


def _fetch_yfinance(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Try yfinance library as primary fetcher."""
    try:
        import yfinance as yf
        end_dt  = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        end_buf = end_dt.strftime("%Y-%m-%d")
        df = yf.download(ticker, start=start, end=end_buf,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        # Normalise date column
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning(f"yfinance failed for {ticker}: {e}")
        return None


def fetch_and_cache(ticker: str, start: str, end: str, db: Session) -> bool:
    """Fetch OHLCV data and cache in DB. Tries yfinance first, then direct API."""
    ticker = ticker.upper().strip()

    # Try yfinance first, then fall back to direct HTTP fetch
    df = _fetch_yfinance(ticker, start, end)
    if df is None or df.empty:
        logger.info(f"yfinance failed for {ticker}, trying direct Yahoo API…")
        df = _fetch_yahoo_direct(ticker, start, end)

    if df is None or df.empty:
        logger.error(f"All fetch methods failed for {ticker} ({start}→{end})")
        return False

    try:
        saved = 0
        for _, row in df.iterrows():
            date_str = str(row["date"])[:10]
            existing = db.query(PriceCache).filter_by(
                ticker=ticker, date=date_str
            ).first()
            if existing:
                continue
            bar = PriceCache(
                ticker=ticker,
                date=date_str,
                open=float(row.get("open", 0) or 0),
                high=float(row.get("high", 0) or 0),
                low=float(row.get("low",  0) or 0),
                close=float(row.get("close", 0) or 0),
                volume=float(row.get("volume", 0) or 0),
            )
            db.add(bar)
            saved += 1
        db.commit()
        logger.info(f"Cached {saved} bars for {ticker} ({start}→{end})")
        return saved > 0
    except Exception as e:
        logger.error(f"DB write error for {ticker}: {e}")
        db.rollback()
        return False


def _date_str(d) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")


def _is_nyse_holiday(d: datetime) -> bool:
    """Return True if the date is a NYSE holiday."""
    y, m, day = d.year, d.month, d.day

    # New Year's Day (and observed)
    if m == 1  and day == 1: return True
    if m == 12 and day == 31 and d.weekday() == 4: return True
    if m == 1  and day == 2  and d.weekday() == 0: return True

    # MLK Day — 3rd Monday of January (since 1998)
    if y >= 1998 and m == 1 and d.weekday() == 0 and 15 <= day <= 21:
        return True

    # Presidents Day — 3rd Monday of February
    if m == 2 and d.weekday() == 0 and 15 <= day <= 21:
        return True

    # Good Friday
    easter = _easter(y)
    good_friday = easter - timedelta(days=2)
    if d.date() == good_friday.date():
        return True

    # Memorial Day — last Monday of May
    if m == 5 and d.weekday() == 0 and day >= 25:
        return True

    # Juneteenth (since 2022)
    if y >= 2022 and m == 6 and day == 19: return True
    if y >= 2022 and m == 6 and day == 18 and d.weekday() == 4: return True
    if y >= 2022 and m == 6 and day == 20 and d.weekday() == 0: return True

    # Independence Day
    if m == 7 and day == 4: return True
    if m == 7 and day == 3 and d.weekday() == 4: return True
    if m == 7 and day == 5 and d.weekday() == 0: return True

    # Labor Day — 1st Monday of September
    if m == 9 and d.weekday() == 0 and day <= 7:
        return True

    # Thanksgiving — 4th Thursday of November
    if m == 11 and d.weekday() == 3 and 22 <= day <= 28:
        return True

    # Christmas
    if m == 12 and day == 25: return True
    if m == 12 and day == 24 and d.weekday() == 4: return True
    if m == 12 and day == 26 and d.weekday() == 0: return True

    return False


def _easter(year: int) -> datetime:
    """Compute Easter Sunday (Anonymous Gregorian algorithm)."""
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


def get_trading_days(start: str, end: str, db: Session,
                     reference_ticker: str = "SPY") -> List[str]:
    """Return NYSE trading days between start and end. Pure Python — no network call."""
    # Check cache first
    any_cached = (
        db.query(PriceCache.date)
        .filter(PriceCache.date >= start, PriceCache.date <= end)
        .limit(1).first()
    )
    if any_cached:
        cached = (
            db.query(PriceCache.date)
            .filter(PriceCache.date >= start, PriceCache.date <= end)
            .order_by(PriceCache.date).distinct().all()
        )
        if cached:
            return [r.date for r in cached]

    # Pure-Python NYSE calendar
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")
    days = []
    cur = start_dt
    while cur <= end_dt:
        if cur.weekday() < 5 and not _is_nyse_holiday(cur):
            days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return days


def get_price_bar(ticker: str, date: str, db: Session) -> Optional[Dict]:
    ticker = ticker.upper()
    bar = db.query(PriceCache).filter_by(ticker=ticker, date=date).first()
    if bar:
        return {"date": bar.date, "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close, "volume": bar.volume}
    return None


def get_close_price(ticker: str, date: str, db: Session) -> Optional[float]:
    """Get closing price — falls back to nearest prior date if exact not found."""
    bar = get_price_bar(ticker, date, db)
    if bar:
        return bar["close"]
    row = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker.upper(), PriceCache.date <= date)
        .order_by(PriceCache.date.desc()).first()
    )
    return row.close if row else None


def get_chart_data(ticker: str, from_date: str, to_date: str,
                   db: Session) -> List[Dict]:
    ticker = ticker.upper()
    existing_count = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker,
                PriceCache.date >= from_date,
                PriceCache.date <= to_date)
        .count()
    )
    if existing_count == 0:
        fetch_and_cache(ticker, from_date, to_date, db)

    bars = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker,
                PriceCache.date >= from_date,
                PriceCache.date <= to_date)
        .order_by(PriceCache.date).all()
    )
    return [{"date": b.date, "open": b.open, "high": b.high,
             "low": b.low, "close": b.close, "volume": b.volume}
            for b in bars]


def ensure_ticker_data(ticker: str, start: str, end: str,
                       db: Session) -> bool:
    ticker = ticker.upper()
    count = db.query(PriceCache).filter(
        PriceCache.ticker == ticker,
        PriceCache.date >= start,
        PriceCache.date <= end,
    ).count()
    if count > 0:
        return True
    return fetch_and_cache(ticker, start, end, db)


def validate_ticker(ticker: str) -> bool:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker.upper()).fast_info
        return hasattr(info, "last_price") and info.last_price is not None
    except Exception:
        return False


# Popular tickers for autocomplete
POPULAR_TICKERS = [
    {"symbol": "AAPL",  "name": "Apple Inc."},
    {"symbol": "MSFT",  "name": "Microsoft Corp."},
    {"symbol": "GOOGL", "name": "Alphabet Inc."},
    {"symbol": "AMZN",  "name": "Amazon.com Inc."},
    {"symbol": "TSLA",  "name": "Tesla Inc."},
    {"symbol": "NVDA",  "name": "NVIDIA Corp."},
    {"symbol": "META",  "name": "Meta Platforms"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    {"symbol": "JPM",   "name": "JPMorgan Chase"},
    {"symbol": "V",     "name": "Visa Inc."},
    {"symbol": "JNJ",   "name": "Johnson & Johnson"},
    {"symbol": "WMT",   "name": "Walmart Inc."},
    {"symbol": "PG",    "name": "Procter & Gamble"},
    {"symbol": "MA",    "name": "Mastercard Inc."},
    {"symbol": "UNH",   "name": "UnitedHealth Group"},
    {"symbol": "HD",    "name": "Home Depot"},
    {"symbol": "DIS",   "name": "Walt Disney Co."},
    {"symbol": "BAC",   "name": "Bank of America"},
    {"symbol": "NFLX",  "name": "Netflix Inc."},
    {"symbol": "ADBE",  "name": "Adobe Inc."},
    {"symbol": "CRM",   "name": "Salesforce Inc."},
    {"symbol": "AMD",   "name": "Advanced Micro Devices"},
    {"symbol": "INTC",  "name": "Intel Corp."},
    {"symbol": "PYPL",  "name": "PayPal Holdings"},
    {"symbol": "SPOT",  "name": "Spotify Technology"},
    {"symbol": "UBER",  "name": "Uber Technologies"},
    {"symbol": "COIN",  "name": "Coinbase Global"},
    {"symbol": "SQ",    "name": "Block Inc."},
    {"symbol": "SHOP",  "name": "Shopify Inc."},
    {"symbol": "ZM",    "name": "Zoom Video"},
    {"symbol": "PLTR",  "name": "Palantir Technologies"},
    {"symbol": "SPY",   "name": "S&P 500 ETF"},
    {"symbol": "QQQ",   "name": "Nasdaq 100 ETF"},
    {"symbol": "GLD",   "name": "Gold ETF"},
    {"symbol": "XOM",   "name": "Exxon Mobil"},
    {"symbol": "CVX",   "name": "Chevron Corp."},
    {"symbol": "PFE",   "name": "Pfizer Inc."},
    {"symbol": "MRNA",  "name": "Moderna Inc."},
    {"symbol": "BA",    "name": "Boeing Co."},
    {"symbol": "GE",    "name": "General Electric"},
    {"symbol": "F",     "name": "Ford Motor Co."},
    {"symbol": "GM",    "name": "General Motors"},
    {"symbol": "RIVN",  "name": "Rivian Automotive"},
]