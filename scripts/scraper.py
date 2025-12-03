import requests
import pandas as pd
from datetime import datetime
import sys
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Add the parent directory to the Python path to allow for imports from 'backend'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.database import engine, DailyOHLCV
except ImportError:
    print("Error: Could not import from backend.database. Make sure the backend directory is in the Python path.")
    sys.exit(1)

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

        df['symbol'] = symbol
        df['date'] = df['date'].apply(lambda d: datetime.strptime(f"{int(d.split('/')[0]) + 1911}/{d.split('/')[1]}/{d.split('/')[2]}", '%Y/%m/%d').date())

        numeric_cols = ['volume', 'open', 'high', 'low', 'close']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        df['volume'] = df['volume'].astype(int)

        print(f"Successfully scraped {len(df)} records for symbol {symbol} for month {date_str[:6]}")
        return df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]

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
    if df.empty:
        print("DataFrame is empty, skipping database load.")
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
                    INSERT INTO {DailyOHLCV.__tablename__} (date, symbol, open, high, low, close, volume)
                    SELECT date, symbol, open, high, low, close, volume FROM {temp_table_name}
                    ON CONFLICT (date, symbol) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume;
                """
                conn.execute(text(upsert_sql))
                print(f"Successfully loaded/updated {len(df)} records for symbols {df['symbol'].unique()} into the database.")
    except Exception as e:
        print(f"Failed to load data into database: {e}")

if __name__ == "__main__":
    test_symbol = "2330"  # TSMC

    print(f"--- Running Test Scrape for Symbol: {test_symbol} ---")
    scraped_df = scrape_twse_data(symbol=test_symbol)

    if not scraped_df.empty:
        print("\n--- Scraped Data Sample ---")
        print(scraped_df.head())

        print("\n--- Loading Data to Database ---")
        # To run this part, the database service must be running.
        # e.g., via `docker-compose up -d`
        load_to_db(scraped_df)
    else:
        print("\n--- No data was scraped, skipping database load. ---")
