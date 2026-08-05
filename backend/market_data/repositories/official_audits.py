from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from backend.database import RawIngestAudit, SessionLocal
from backend.platform.errors import DataAccessError


def list_official_audit_metadata(
    *,
    market: str,
    source_names: Iterable[str],
    fetch_timestamp_floor: datetime,
) -> list[tuple[int, str, str, str]]:
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    RawIngestAudit.id,
                    RawIngestAudit.source_name,
                    RawIngestAudit.fetch_status,
                    RawIngestAudit.expected_symbol_context,
                )
                .where(RawIngestAudit.market == market)
                .where(RawIngestAudit.source_name.in_(tuple(source_names)))
                .where(RawIngestAudit.fetch_timestamp >= fetch_timestamp_floor)
                .order_by(
                    RawIngestAudit.fetch_timestamp.asc(), RawIngestAudit.id.asc()
                )
            )
            return [
                (
                    row.id,
                    row.source_name,
                    row.fetch_status,
                    row.expected_symbol_context,
                )
                for row in rows
            ]
    except Exception as exc:
        raise DataAccessError("Failed to load official ingest audit metadata.") from exc


def load_audit_payloads(audit_ids: Iterable[int]) -> dict[int, str | None]:
    ids = list(audit_ids)
    if not ids:
        return {}
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(RawIngestAudit.id, RawIngestAudit.payload_body).where(
                    RawIngestAudit.id.in_(ids)
                )
            )
            return {row.id: row.payload_body for row in rows}
    except Exception as exc:
        raise DataAccessError("Failed to load official ingest audit payloads.") from exc
