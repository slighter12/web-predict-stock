from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import desc, func, select

from scripts import scraper

from ..database import DailyOHLCV, RawIngestAudit, SessionLocal
from ..errors import DataAccessError, DataNotFoundError

logger = logging.getLogger(__name__)


def get_raw_ingest_record(raw_payload_id: int) -> RawIngestAudit:
    try:
        with SessionLocal() as session:
            row = session.get(RawIngestAudit, raw_payload_id)
            if row is None:
                raise DataNotFoundError(
                    f"Raw payload '{raw_payload_id}' was not found."
                )
            return row
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to load raw ingest record raw_payload_id=%s", raw_payload_id
        )
        raise DataAccessError("Failed to load raw ingest record.") from exc


def get_latest_successful_raw_ingest() -> RawIngestAudit:
    return get_latest_successful_raw_ingest_for_scope()


def get_latest_successful_raw_ingest_for_scope(
    market: str | None = None, symbol: str | None = None
) -> RawIngestAudit:
    try:
        with SessionLocal() as session:
            stmt = (
                select(RawIngestAudit)
                .where(RawIngestAudit.fetch_status == scraper.FETCH_STATUS_SUCCESS)
                .where(RawIngestAudit.payload_body.is_not(None))
                .where(RawIngestAudit.payload_body != "")
            )
            if market:
                stmt = stmt.where(RawIngestAudit.market == market)
            if symbol:
                stmt = stmt.where(RawIngestAudit.symbol == symbol)
            stmt = stmt.order_by(
                desc(RawIngestAudit.fetch_timestamp), desc(RawIngestAudit.id)
            ).limit(1)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                scope_parts = []
                if market:
                    scope_parts.append(f"market '{market}'")
                if symbol:
                    scope_parts.append(f"symbol '{symbol}'")
                scope_suffix = f" for {' '.join(scope_parts)}" if scope_parts else ""
                raise DataNotFoundError(
                    f"No replayable raw payload is available{scope_suffix}."
                )
            return row
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to load latest successful raw ingest record market=%s symbol=%s",
            market,
            symbol,
        )
        raise DataAccessError(
            "Failed to load latest successful raw ingest record."
        ) from exc


def get_completed_trading_day_delta(market: str, latest_replayable_day: date) -> int:
    try:
        with SessionLocal() as session:
            stmt = select(func.count(func.distinct(DailyOHLCV.date))).where(
                DailyOHLCV.market == market,
                DailyOHLCV.date > latest_replayable_day,
            )
            delta = session.execute(stmt).scalar_one()
            return int(delta or 0)
    except Exception as exc:
        logger.exception(
            "Failed to calculate completed trading day delta market=%s latest_day=%s",
            market,
            latest_replayable_day,
        )
        raise DataAccessError(
            "Failed to calculate completed trading day delta."
        ) from exc


def list_market_trading_days(
    market: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    descending: bool = False,
) -> list[date]:
    try:
        with SessionLocal() as session:
            stmt = select(func.distinct(DailyOHLCV.date)).where(
                DailyOHLCV.market == market
            )
            if start_date is not None:
                stmt = stmt.where(DailyOHLCV.date >= start_date)
            if end_date is not None:
                stmt = stmt.where(DailyOHLCV.date <= end_date)
            order_by_clause = desc(DailyOHLCV.date) if descending else DailyOHLCV.date
            stmt = stmt.order_by(order_by_clause)
            if limit is not None:
                stmt = stmt.limit(limit)
            return [
                item
                for item in session.execute(stmt).scalars().all()
                if item is not None
            ]
    except Exception as exc:
        logger.exception(
            "Failed to list market trading days market=%s start_date=%s end_date=%s",
            market,
            start_date,
            end_date,
        )
        raise DataAccessError("Failed to list market trading days.") from exc
