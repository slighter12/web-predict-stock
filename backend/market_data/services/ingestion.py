from __future__ import annotations

import logging

from backend.market_data.contracts.operations import DataIngestionRequest
from backend.market_data.services._normalization import clean_optional_text
from backend.platform.errors import DataAccessError, UnsupportedConfigurationError
from scripts import market_data_ingestion as scraper

logger = logging.getLogger(__name__)


def ingest_market_data(request: DataIngestionRequest) -> dict:
    symbol = request.symbol.strip().upper()
    market = request.market.strip().upper()
    date_str = clean_optional_text(request.date_str)

    logger.info(
        "Starting market data ingestion symbol=%s market=%s years=%s",
        symbol,
        market,
        request.years,
    )
    try:
        summary = scraper.ingest_symbol(
            symbol=symbol,
            market=market,
            years=request.years,
            date_str=date_str,
        )
    except ValueError as exc:
        logger.warning(
            "Market data ingestion rejected symbol=%s market=%s reason=%s",
            symbol,
            market,
            exc,
        )
        raise UnsupportedConfigurationError(str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Market data ingestion failed symbol=%s market=%s", symbol, market
        )
        raise DataAccessError("Failed to ingest market data.") from exc

    logger.info(
        "Completed market data ingestion symbol=%s market=%s backfill_raw_payload_id=%s daily_raw_payload_id=%s",
        symbol,
        market,
        summary["backfill"].get("raw_payload_id"),
        summary["daily_update"].get("raw_payload_id"),
    )
    return summary
