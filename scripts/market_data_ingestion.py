"""Compatibility command entry point for the backend ingestion runtime."""

from __future__ import annotations

import os

from backend.market_data.services import ingestion_runtime as _runtime


def _main() -> None:
    print(
        "Run 'uv run alembic upgrade head' to create or migrate database tables "
        "before ingesting."
    )
    symbol = os.getenv("INGEST_SYMBOL", "2330")
    market = os.getenv("INGEST_MARKET", _runtime.MARKET_TW).upper()
    years = int(os.getenv("INGEST_YEARS", "5"))
    date_str = os.getenv("INGEST_DATE")
    _runtime.logger.info(
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
