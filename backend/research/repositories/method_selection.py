from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import datetime
from typing import Any

from backend.database import MethodSelectionMatrix, SessionLocal
from backend.platform.db.repository_helpers import (
    clone_payload,
    json_dumps,
    json_loads,
    normalize_created_at,
)
from backend.platform.errors import DataAccessError, DataNotFoundError
from backend.platform.time import utc_now
from backend.research.repositories.runs import persist_research_run_record

logger = logging.getLogger(__name__)


def persist_method_selection_matrix(
    payload: dict[str, Any], *, session: Any | None = None, commit: bool = True
) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("created_at", utc_now())
    try:
        session_context = SessionLocal() if session is None else nullcontext(session)
        with session_context as session:
            row = session.get(MethodSelectionMatrix, record["matrix_id"])
            if row is None:
                row = MethodSelectionMatrix(matrix_id=record["matrix_id"])
            row.request_id = record["request_id"]
            row.status = record["status"]
            row.request_payload_json = json_dumps(record["request"]) or "{}"
            row.result_payload_json = json_dumps(record) or "{}"
            created_at = record.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            row.created_at = normalize_created_at(created_at)
            session.add(row)
            if commit:
                session.commit()
                session.refresh(row)
            return json_loads(row.result_payload_json, record)
    except Exception as exc:
        logger.exception("Failed to persist Method Selection Matrix matrix_id=%s", record.get("matrix_id"))
        raise DataAccessError("Failed to persist Method Selection Matrix.") from exc


def persist_method_selection_batch(
    matrix_payload: dict[str, Any],
    research_run_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist promoted runs and their Matrix in one transaction."""
    try:
        with SessionLocal() as session:
            try:
                for payload in research_run_payloads:
                    persist_research_run_record(payload, session=session, commit=False)
                persisted = persist_method_selection_matrix(
                    matrix_payload,
                    session=session,
                    commit=False,
                )
                session.commit()
                return persisted
            except Exception:
                session.rollback()
                raise
    except Exception as exc:
        logger.exception(
            "Failed to persist Method Selection Matrix batch matrix_id=%s",
            matrix_payload.get("matrix_id"),
        )
        raise DataAccessError(
            "Failed to persist Method Selection Matrix batch."
        ) from exc


def get_method_selection_matrix_snapshot(matrix_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(MethodSelectionMatrix, matrix_id)
            if row is None:
                raise DataNotFoundError(f"Method Selection Matrix '{matrix_id}' was not found.")
            payload = json_loads(row.result_payload_json, None)
            if not isinstance(payload, dict):
                raise DataAccessError(
                    f"Method Selection Matrix '{matrix_id}' has invalid persisted content."
                )
            return payload
    except (DataNotFoundError, DataAccessError):
        raise
    except Exception as exc:
        logger.exception("Failed to load Method Selection Matrix matrix_id=%s", matrix_id)
        raise DataAccessError("Failed to load Method Selection Matrix.") from exc
