from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from backend.database import IngestionWatchlist, SessionLocal
from backend.platform.db.repository_helpers import normalize_created_at
from backend.platform.errors import DataAccessError

logger = logging.getLogger(__name__)


def _watchlist_row_to_dict(row: IngestionWatchlist) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "market": row.market,
        "years": row.years,
        "is_active": row.is_active,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_watchlist_entry(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(IngestionWatchlist)
                .where(IngestionWatchlist.symbol == payload["symbol"])
                .where(IngestionWatchlist.market == payload["market"])
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none() or IngestionWatchlist()
            row.symbol = payload["symbol"]
            row.market = payload["market"]
            row.years = payload["years"]
            row.is_active = payload.get("is_active", True)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _watchlist_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist ingestion watchlist symbol=%s market=%s",
            payload["symbol"],
            payload["market"],
        )
        raise DataAccessError("Failed to persist ingestion watchlist entry.") from exc


def list_watchlist_entries(
    limit: int = 200, *, active_only: bool = False
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(IngestionWatchlist)
            if active_only:
                stmt = stmt.where(IngestionWatchlist.is_active.is_(True))
            stmt = stmt.order_by(
                desc(IngestionWatchlist.created_at), desc(IngestionWatchlist.id)
            ).limit(limit)
            return [
                _watchlist_row_to_dict(row) for row in session.execute(stmt).scalars()
            ]
    except Exception as exc:
        logger.exception("Failed to list ingestion watchlist entries from DB")
        raise DataAccessError("Failed to list ingestion watchlist entries.") from exc
