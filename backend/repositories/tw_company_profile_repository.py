from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, func, select

from ..database import SessionLocal, TwCompanyProfile
from ..errors import DataAccessError
from ._shared import clone_payload, normalize_created_at

logger = logging.getLogger(__name__)


def _row_to_dict(row: TwCompanyProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "market": row.market,
        "exchange": row.exchange,
        "board": row.board,
        "company_name": row.company_name,
        "isin_code": row.isin_code,
        "industry_category": row.industry_category,
        "listing_date": row.listing_date,
        "trading_status": row.trading_status,
        "source_name": row.source_name,
        "raw_payload_id": row.raw_payload_id,
        "archive_object_reference": row.archive_object_reference,
        "notes": row.notes,
        "created_at": normalize_created_at(row.created_at),
        "updated_at": normalize_created_at(row.updated_at),
    }


def upsert_tw_company_profile(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    tracked_fields = (
        "market",
        "exchange",
        "board",
        "company_name",
        "isin_code",
        "industry_category",
        "listing_date",
        "trading_status",
        "source_name",
        "raw_payload_id",
        "archive_object_reference",
        "notes",
    )
    try:
        with SessionLocal() as session:
            stmt = (
                select(TwCompanyProfile)
                .where(TwCompanyProfile.symbol == record["symbol"])
                .where(TwCompanyProfile.exchange == record["exchange"])
            )
            row = session.execute(stmt).scalar_one_or_none()
            write_action = "created" if row is None else "noop"
            if row is None:
                row = TwCompanyProfile()
            else:
                if any(getattr(row, field) != record.get(field) for field in tracked_fields):
                    write_action = "updated"
            row.symbol = record["symbol"]
            row.market = record["market"]
            row.exchange = record["exchange"]
            row.board = record["board"]
            row.company_name = record["company_name"]
            row.isin_code = record.get("isin_code")
            row.industry_category = record.get("industry_category")
            row.listing_date = record.get("listing_date")
            row.trading_status = record["trading_status"]
            row.source_name = record["source_name"]
            row.raw_payload_id = record.get("raw_payload_id")
            row.archive_object_reference = record.get("archive_object_reference")
            row.notes = record.get("notes")
            session.add(row)
            session.commit()
            session.refresh(row)
            persisted = _row_to_dict(row)
            persisted["write_action"] = write_action
            return persisted
    except Exception as exc:
        logger.exception(
            "Failed to persist TW company profile symbol=%s exchange=%s",
            record.get("symbol"),
            record.get("exchange"),
        )
        raise DataAccessError("Failed to persist TW company profile.") from exc


def list_tw_company_profiles(
    *,
    limit: int = 200,
    offset: int = 0,
    trading_status: str | None = None,
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(TwCompanyProfile)
            if trading_status is not None:
                stmt = stmt.where(TwCompanyProfile.trading_status == trading_status)
            stmt = stmt.order_by(
                TwCompanyProfile.exchange.asc(),
                TwCompanyProfile.symbol.asc(),
                desc(TwCompanyProfile.updated_at),
            ).offset(offset)
            if limit > 0:
                stmt = stmt.limit(limit)
            return [_row_to_dict(row) for row in session.execute(stmt).scalars().all()]
    except Exception as exc:
        logger.exception("Failed to list TW company profiles")
        raise DataAccessError("Failed to list TW company profiles.") from exc


def count_tw_company_profiles(*, trading_status: str | None = None) -> int:
    try:
        with SessionLocal() as session:
            stmt = select(func.count(TwCompanyProfile.id))
            if trading_status is not None:
                stmt = stmt.where(TwCompanyProfile.trading_status == trading_status)
            return int(session.execute(stmt).scalar_one() or 0)
    except Exception as exc:
        logger.exception("Failed to count TW company profiles")
        raise DataAccessError("Failed to count TW company profiles.") from exc
