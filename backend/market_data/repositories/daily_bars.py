from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

import pandas as pd
from sqlalchemy import select

from backend.database import DailyOHLCV, engine
from backend.platform.errors import DataAccessError

logger = logging.getLogger(__name__)


def get_data(
    symbols: str | Sequence[str],
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    market: str | None = None,
) -> pd.DataFrame:
    symbol_list = [symbols] if isinstance(symbols, str) else list(symbols)
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
            frame = pd.read_sql(query, connection)
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

    if frame.empty:
        logger.info(
            "No OHLCV rows found symbols=%s market=%s start=%s end=%s source=%s",
            symbol_list,
            market,
            start_date,
            end_date,
            source,
        )
        return pd.DataFrame()

    frame.set_index("date" if len(symbol_list) == 1 else ["date", "symbol"], inplace=True)
    logger.info("Fetched OHLCV rows=%s symbols=%s", len(frame), symbol_list)
    return frame
