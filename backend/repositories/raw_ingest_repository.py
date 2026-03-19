from __future__ import annotations

import logging

from sqlalchemy import desc, select

from scripts import scraper

from ..database import RawIngestAudit, SessionLocal
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
    try:
        with SessionLocal() as session:
            stmt = (
                select(RawIngestAudit)
                .where(RawIngestAudit.fetch_status == scraper.FETCH_STATUS_SUCCESS)
                .where(RawIngestAudit.payload_body.is_not(None))
                .where(RawIngestAudit.payload_body != "")
                .order_by(desc(RawIngestAudit.fetch_timestamp), desc(RawIngestAudit.id))
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                raise DataNotFoundError("No replayable raw payload is available.")
            return row
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load latest successful raw ingest record")
        raise DataAccessError(
            "Failed to load latest successful raw ingest record."
        ) from exc
