from __future__ import annotations

from scripts import scraper


def ingest_market_data(
    symbol: str, market: str, years: int, date_str: str | None
) -> dict:
    return scraper.ingest_symbol(
        symbol=symbol, market=market, years=years, date_str=date_str
    )
