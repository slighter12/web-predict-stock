from __future__ import annotations

import logging

from ..repositories.ingestion_watchlist_repository import (
    list_watchlist_entries,
    persist_watchlist_entry,
)
from ..schemas.data_plane import IngestionWatchlistRequest
from ._normalization import clean_required_text

logger = logging.getLogger(__name__)


def create_ingestion_watchlist_entry(request: IngestionWatchlistRequest) -> dict:
    payload = {
        "symbol": clean_required_text(request.symbol).upper(),
        "market": clean_required_text(request.market).upper(),
        "years": request.years,
        "is_active": True,
    }
    logger.info(
        "Creating ingestion watchlist entry symbol=%s market=%s years=%s",
        payload["symbol"],
        payload["market"],
        payload["years"],
    )
    return persist_watchlist_entry(payload)


def list_ingestion_watchlist(limit: int = 200) -> list[dict]:
    return list_watchlist_entries(limit=limit)
