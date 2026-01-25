import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import text

# Add the parent directory to the Python path to allow for imports from 'backend'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.database import DailyOHLCV, create_tables, engine
except ImportError:
    print("Error: Could not import from backend.database. Make sure the backend directory is in the Python path.")
    sys.exit(1)

SOURCE_TWSE = "twse"
SOURCE_YFINANCE = "yfinance"
MARKET_TW = "TW"
MARKET_US = "US"


def to_yfinance_ticker(symbol: str, market: str) -> str:
    market_code = (market or "").upper()
    if market_code == MARKET_TW and "." not in symbol:
        return f"{symbol}.TW"
    return symbol


def validate_ohlcv(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    if df.empty:
        return df

    required_cols = ["date", "symbol", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"Missing columns in OHLCV data {label}: {missing}")
        return pd.DataFrame()

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.drop_duplicates(subset=["date", "symbol"], keep="last")

    null_rows = df[required_cols].isnull().any(axis=1)
    if null_rows.any():
        print(f"Null OHLCV rows found {label}: {int(null_rows.sum())}")
        df = df[~null_rows]

    invalid_price = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    invalid_volume = df["volume"] < 0
    invalid_rows = invalid_price | invalid_volume
    if invalid_rows.any():
        print(f"Invalid OHLCV values found {label}: {int(invalid_rows.sum())}")
        df = df[~invalid_rows]

    if len(df) > 1:
        sorted_dates = pd.to_datetime(df["date"]).sort_values()
        gap_days = sorted_dates.diff().dt.days
        gap_count = (gap_days > 7).sum()
        if gap_count:
            print(f"Warning: {int(gap_count)} gaps >7 days detected {label}")

    return df


def scrape_twse_data(symbol: str, date_str: str = None) -> pd.DataFrame:
    """
    Scrapes daily OHLCV data for a given stock symbol from the TWSE for a specific month.
    :param symbol: The stock symbol (e.g., "2330").
    :param date_str: The date in "YYYYMMDD" format, defaults to the current date.
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')

    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={symbol}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()

        if data['stat'] != 'OK':
            print(f"Failed to fetch data for {symbol}: {data.get('note', 'No data found')}")
            return pd.DataFrame()

        df = pd.DataFrame(data['data'], columns=data['fields'])

        # --- Data Cleaning ---
        column_mapping = {
            '日期': 'date', '成交股數': 'volume', '成交金額': 'trade_value', '開盤價': 'open',
            '最高價': 'high', '最低價': 'low', '收盤價': 'close', '漲跌價差': 'price_change',
            '成交筆數': 'trade_count',
        }
        df.rename(columns=column_mapping, inplace=True)

        df["symbol"] = symbol
        df["source"] = SOURCE_TWSE
        df["market"] = MARKET_TW
        df['date'] = df['date'].apply(lambda d: datetime.strptime(f"{int(d.split('/')[0]) + 1911}/{d.split('/')[1]}/{d.split('/')[2]}", '%Y/%m/%d').date())

        numeric_cols = ['volume', 'open', 'high', 'low', 'close']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        df['volume'] = df['volume'].astype(int)

        print(f"Successfully scraped {len(df)} records for symbol {symbol} for month {date_str[:6]}")
        df = df[['date', 'symbol', 'market', 'source', 'open', 'high', 'low', 'close', 'volume']]
        return validate_ohlcv(df, label=f"{symbol}:{SOURCE_TWSE}")

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed for symbol {symbol}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"An unexpected error occurred during scraping for {symbol}: {e}")
        return pd.DataFrame()

def load_to_db(df: pd.DataFrame):
    """
    Loads a DataFrame with OHLCV data into the database using an "upsert" method.
    """
    df = validate_ohlcv(df, label="load_to_db")
    if df.empty:
        print("DataFrame is empty, skipping database load.")
        return

    required_cols = ["date", "symbol", "market", "source", "open", "high", "low", "close", "volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Missing columns for DB load: {missing_cols}")
        return

    temp_table_name = "daily_ohlcv_temp"
    try:
        # Use a connection from the engine
        with engine.connect() as conn:
            with conn.begin(): # Start a transaction
                # Create a temporary table and insert the new data
                df.to_sql(temp_table_name, conn, if_exists='replace', index=False)

                # Use PostgreSQL's ON CONFLICT to perform an upsert
                upsert_sql = f"""
                    INSERT INTO {DailyOHLCV.__tablename__} (
                        date, symbol, market, source, open, high, low, close, volume
                    )
                    SELECT date, symbol, market, source, open, high, low, close, volume
                    FROM {temp_table_name}
                    ON CONFLICT (date, symbol) DO UPDATE SET
                        market = EXCLUDED.market,
                        source = EXCLUDED.source,
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                    WHERE EXCLUDED.source = '{SOURCE_TWSE}'
                        OR {DailyOHLCV.__tablename__}.source IS NULL
                        OR {DailyOHLCV.__tablename__}.source != '{SOURCE_TWSE}';
                """
                conn.execute(text(upsert_sql))
                print(f"Successfully loaded/updated {len(df)} records for symbols {df['symbol'].unique()} into the database.")
    except Exception as e:
        print(f"Failed to load data into database: {e}")


def scrape_daily_twse(symbol: str, date_str: str = None) -> pd.DataFrame:
    """
    Fetch the latest available daily record from TWSE by pulling the current month.
    """
    month_df = scrape_twse_data(symbol=symbol, date_str=date_str)
    if month_df.empty:
        return month_df

    latest_date = max(month_df["date"])
    return month_df[month_df["date"] == latest_date].copy()


def backfill_history(symbol: str, years: int = 5, market: str = MARKET_TW) -> pd.DataFrame:
    """
    Backfill OHLCV data using yfinance for the requested lookback window.
    """
    if years < 1:
        raise ValueError("years must be >= 1")

    ticker_symbol = to_yfinance_ticker(symbol, market)
    start_date = datetime.utcnow() - timedelta(days=365 * years)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start_date, auto_adjust=False, actions=False)
    except Exception as e:
        print(f"Failed to fetch yfinance data for {ticker_symbol}: {e}")
        return pd.DataFrame()

    if hist.empty:
        print(f"No yfinance data returned for {ticker_symbol}.")
        return pd.DataFrame()

    hist = hist.reset_index()
    hist.rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        },
        inplace=True,
    )

    for col in ["open", "high", "low", "close", "volume"]:
        hist[col] = pd.to_numeric(hist[col], errors="coerce")

    hist["date"] = pd.to_datetime(hist["date"]).dt.date
    hist["symbol"] = symbol
    hist["source"] = SOURCE_YFINANCE
    hist["market"] = market
    hist["volume"] = hist["volume"].fillna(0).astype(int)

    hist = hist[["date", "symbol", "market", "source", "open", "high", "low", "close", "volume"]]
    return validate_ohlcv(hist, label=f"{symbol}:{SOURCE_YFINANCE}")

if __name__ == "__main__":
    test_symbol = "2330"  # TSMC

    create_tables()

    print(f"--- Running yfinance backfill for symbol: {test_symbol} ---")
    backfill_df = backfill_history(symbol=test_symbol, years=5, market=MARKET_TW)
    if not backfill_df.empty:
        load_to_db(backfill_df)

    print(f"--- Running TWSE daily update for symbol: {test_symbol} ---")
    daily_df = scrape_daily_twse(symbol=test_symbol)
    if not daily_df.empty:
        load_to_db(daily_df)
