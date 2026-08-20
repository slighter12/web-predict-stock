from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.database import CalibrationMatrix, SessionLocal
from backend.platform.db.repository_helpers import (
    clone_payload,
    json_dumps,
    json_loads,
    normalize_created_at,
)
from backend.platform.errors import DataAccessError, DataNotFoundError
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)


def _coerce_created_at(value: Any) -> datetime | None:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def persist_calibration_matrix(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("created_at", utc_now())
    try:
        with SessionLocal() as session:
            row = session.get(CalibrationMatrix, record["matrix_id"])
            if row is None:
                row = CalibrationMatrix(matrix_id=record["matrix_id"])
            row.request_id = record["request_id"]
            row.status = record["status"]
            row.request_payload_json = json_dumps(record["request"]) or "{}"
            row.result_payload_json = json_dumps(record) or "{}"
            row.created_at = normalize_created_at(
                _coerce_created_at(record.get("created_at"))
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return json_loads(row.result_payload_json, record)
    except Exception as exc:
        logger.exception(
            "Failed to persist Calibration Matrix matrix_id=%s",
            record.get("matrix_id"),
        )
        raise DataAccessError("Failed to persist Calibration Matrix.") from exc


def get_calibration_matrix_snapshot(matrix_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(CalibrationMatrix, matrix_id)
            if row is None:
                raise DataNotFoundError(
                    f"Calibration Matrix '{matrix_id}' was not found."
                )
            payload = json_loads(row.result_payload_json, None)
            if not isinstance(payload, dict):
                raise DataAccessError(
                    f"Calibration Matrix '{matrix_id}' has invalid persisted content."
                )
            return payload
    except DataNotFoundError:
        raise
    except DataAccessError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to load Calibration Matrix matrix_id=%s",
            matrix_id,
        )
        raise DataAccessError("Failed to load Calibration Matrix.") from exc
