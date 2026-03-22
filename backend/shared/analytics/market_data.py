import logging
from datetime import date
from typing import Sequence, Union

import pandas as pd
from sqlalchemy import select

# Use a relative import for intra-package dependencies
from backend.database import DailyOHLCV, engine
from backend.platform.errors import DataAccessError

PRICE_COLS = ["open", "high", "low", "close"]
logger = logging.getLogger(__name__)


def apply_price_adjustment(
    df: pd.DataFrame, factor_col: str = "adjust_factor"
) -> pd.DataFrame:
    """
    Return a copy of df with adjusted OHLC columns if an adjustment factor is provided.
    The raw OHLC columns remain unchanged.
    """
    if df.empty or factor_col not in df.columns:
        return df

    adjusted = df.copy()
    factor = pd.to_numeric(adjusted[factor_col], errors="coerce")
    for col in PRICE_COLS:
        adjusted[f"{col}_adj"] = adjusted[col] * factor
    return adjusted


def get_data(
    symbols: Union[str, Sequence[str]],
    start_date: date = None,
    end_date: date = None,
    source: str = None,
    market: str = None,
) -> pd.DataFrame:
    """
    Queries the database for daily OHLCV data for one or more symbols and a date range.

    Args:
        symbols (str | Sequence[str]): The stock symbol(s) to query (e.g., "2330").
        start_date (date, optional): The start date of the query range. Defaults to None.
        end_date (date, optional): The end date of the query range. Defaults to None.
        source (str, optional): Data source filter (e.g., "twse" or "yfinance").
        market (str, optional): Market filter (e.g., "TW" or "US").

    Returns:
        pd.DataFrame: A DataFrame containing the OHLCV data, with the 'date' column as the index.
                      Returns an empty DataFrame if no data is found.
    """
    if isinstance(symbols, str):
        symbol_list = [symbols]
    else:
        symbol_list = list(symbols)

    query = select(DailyOHLCV).where(DailyOHLCV.symbol.in_(symbol_list))
    if start_date:
        query = query.where(DailyOHLCV.date >= start_date)
    if end_date:
        query = query.where(DailyOHLCV.date <= end_date)
    if source:
        query = query.where(DailyOHLCV.source == source)
    if market:
        query = query.where(DailyOHLCV.market == market)
    query = query.order_by(DailyOHLCV.date.asc())

    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
    except Exception as exc:
        logger.exception(
            "Failed to fetch OHLCV data symbols=%s market=%s start=%s end=%s source=%s",
            symbol_list,
            market,
            start_date,
            end_date,
            source,
        )
        raise DataAccessError("Failed to fetch OHLCV data.") from exc

    if df.empty:
        logger.info(
            "No OHLCV rows found symbols=%s market=%s start=%s end=%s source=%s",
            symbol_list,
            market,
            start_date,
            end_date,
            source,
        )
        return pd.DataFrame()

    if len(symbol_list) == 1:
        df.set_index("date", inplace=True)
    else:
        df.set_index(["date", "symbol"], inplace=True)

    logger.info("Fetched OHLCV rows=%s symbols=%s", len(df), symbol_list)
    return df


if __name__ == "__main__":
    # --- Example Usage ---
    # This example assumes you have the database running and have loaded some data,
    # for example, by running `scripts/scraper.py`.

    test_symbol = "2330"

    print(f"--- Fetching all data for symbol: {test_symbol} ---")
    all_data_df = get_data(symbols=test_symbol)

    if not all_data_df.empty:
        print(all_data_df.head())
        print("...")
        print(all_data_df.tail())

    # Example with a date range
    print(f"\n--- Fetching data for symbol: {test_symbol} with a date range ---")
    start = date(2025, 12, 1)
    end = date(2025, 12, 31)
    ranged_data_df = get_data(symbols=test_symbol, start_date=start, end_date=end)

    if not ranged_data_df.empty:
        print(ranged_data_df)
