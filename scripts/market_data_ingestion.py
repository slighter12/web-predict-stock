"""Compatibility command entry point for the backend ingestion runtime."""

from __future__ import annotations

import logging
import os
import sys

from scripts._logging import configure_cli_logging

try:
    from backend.market_data.services import ingestion_runtime as _runtime
except ImportError as exc:
    print(
        "Error: Could not import the market-data ingestion runtime: "
        f"{exc}. Make sure the project dependencies and Python path are configured.",
        file=sys.stderr,
    )
    sys.exit(1)

logger = logging.getLogger(__name__)


def _main() -> None:
    configure_cli_logging()
    print(
        "Run 'uv run alembic upgrade head' to create or migrate database tables "
        "before ingesting."
    )
    symbol = os.getenv("INGEST_SYMBOL", "2330")
    market = os.getenv("INGEST_MARKET", _runtime.MARKET_TW).upper()
    try:
        years = int(os.getenv("INGEST_YEARS", "5"))
        if years < 1:
            raise ValueError
    except ValueError:
        print("Error: INGEST_YEARS must be a positive integer.", file=sys.stderr)
        raise SystemExit(2) from None
    date_str = os.getenv("INGEST_DATE")
    logger.info(
        "Starting ingest symbol=%s market=%s years=%s date_override=%s",
        symbol,
        market,
        years,
        date_str,
    )
    print(
        _runtime.ingest_symbol(
            symbol=symbol,
            market=market,
            years=years,
            date_str=date_str,
        )
    )


if __name__ == "__main__":
    _main()
