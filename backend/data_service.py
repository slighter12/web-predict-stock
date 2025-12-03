import pandas as pd
from sqlalchemy import select
from datetime import date

# Use a relative import for intra-package dependencies
from .database import engine, DailyOHLCV

def get_data(symbol: str, start_date: date = None, end_date: date = None) -> pd.DataFrame:
    """
    Queries the database for daily OHLCV data for a given symbol and date range.

    Args:
        symbol (str): The stock symbol to query (e.g., "2330").
        start_date (date, optional): The start date of the query range. Defaults to None.
        end_date (date, optional): The end date of the query range. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame containing the OHLCV data, with the 'date' column as the index.
                      Returns an empty DataFrame if no data is found.
    """
    try:
        # Build the base query
        query = select(DailyOHLCV).where(DailyOHLCV.symbol == symbol)

        # Add date range filters if they are provided
        if start_date:
            query = query.where(DailyOHLCV.date >= start_date)
        if end_date:
            query = query.where(DailyOHLCV.date <= end_date)

        # Order by date to ensure correct sequence for time-series analysis
        query = query.order_by(DailyOHLCV.date.asc())

        # Execute the query and load data into a DataFrame
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)

        if df.empty:
            print(f"No data found for symbol '{symbol}' in the specified date range.")
            return pd.DataFrame()

        # Set the 'date' column as the index, which is standard for time-series data
        df.set_index('date', inplace=True)

        print(f"Successfully fetched {len(df)} records for symbol '{symbol}'.")
        return df

    except Exception as e:
        print(f"An error occurred while fetching data for symbol '{symbol}': {e}")
        return pd.DataFrame()


if __name__ == '__main__':
    # --- Example Usage ---
    # This example assumes you have the database running and have loaded some data,
    # for example, by running `scripts/scraper.py`.

    test_symbol = "2330"

    print(f"--- Fetching all data for symbol: {test_symbol} ---")
    all_data_df = get_data(symbol=test_symbol)

    if not all_data_df.empty:
        print(all_data_df.head())
        print("...")
        print(all_data_df.tail())

    # Example with a date range
    print(f"\n--- Fetching data for symbol: {test_symbol} with a date range ---")
    start = date(2025, 12, 1)
    end = date(2025, 12, 31)
    ranged_data_df = get_data(symbol=test_symbol, start_date=start, end_date=end)

    if not ranged_data_df.empty:
        print(ranged_data_df)
