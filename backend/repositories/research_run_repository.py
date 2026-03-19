from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from ..database import ResearchRun, SessionLocal
from ..domain.runtime_bundle import build_version_pack_payload
from ..errors import DataAccessError, DataNotFoundError
from ..time_utils import utc_now
from ._shared import (
    clone_payload,
    json_dumps,
    json_loads,
    normalize_created_at,
)

logger = logging.getLogger(__name__)


def _run_row_to_dict(row: ResearchRun) -> dict[str, Any]:
    effective_strategy = None
    if row.effective_threshold is not None and row.effective_top_n is not None:
        effective_strategy = {
            "threshold": row.effective_threshold,
            "top_n": row.effective_top_n,
        }

    payload = {
        "run_id": row.run_id,
        "request_id": row.request_id,
        "status": row.status,
        "market": row.market,
        "symbols": json_loads(row.symbols_json, []),
        "strategy_type": row.strategy_type,
        "runtime_mode": row.runtime_mode,
        "default_bundle_version": row.default_bundle_version,
        "effective_strategy": effective_strategy,
        "allow_proactive_sells": row.allow_proactive_sells,
        "config_sources": json_loads(row.config_sources_json, None),
        "fallback_audit": json_loads(row.fallback_audit_json, None),
        "validation_outcome": json_loads(row.validation_outcome_json, None),
        "rejection_reason": row.rejection_reason,
        "request_payload": json_loads(row.request_payload_json, None),
        "metrics": json_loads(row.metrics_json, None),
        "warnings": json_loads(row.warnings_json, []),
        "created_at": normalize_created_at(row.created_at),
    }
    payload.update(
        build_version_pack_payload(
            {
                "threshold_policy_version": row.threshold_policy_version,
                "price_basis_version": row.price_basis_version,
                "benchmark_comparability_gate": row.benchmark_comparability_gate,
                "comparison_eligibility": row.comparison_eligibility,
            }
        )
    )
    return payload


def persist_research_run_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("symbols", [])
    record.setdefault("warnings", [])
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, record["run_id"]) or ResearchRun(
                run_id=record["run_id"]
            )
            row.request_id = record.get("request_id")
            row.status = record["status"]
            row.market = record.get("market")
            row.symbols_json = json_dumps(record.get("symbols", [])) or "[]"
            row.strategy_type = record.get("strategy_type")
            row.runtime_mode = record.get("runtime_mode")
            row.default_bundle_version = record.get("default_bundle_version")
            effective_strategy = record.get("effective_strategy") or {}
            row.effective_threshold = effective_strategy.get("threshold")
            row.effective_top_n = effective_strategy.get("top_n")
            row.allow_proactive_sells = record.get("allow_proactive_sells")
            row.config_sources_json = json_dumps(record.get("config_sources"))
            row.fallback_audit_json = json_dumps(record.get("fallback_audit"))
            row.validation_outcome_json = json_dumps(record.get("validation_outcome"))
            row.rejection_reason = record.get("rejection_reason")
            row.request_payload_json = json_dumps(record.get("request_payload"))
            row.metrics_json = json_dumps(record.get("metrics"))
            row.warnings_json = json_dumps(record.get("warnings", []))
            row.threshold_policy_version = record.get("threshold_policy_version")
            row.price_basis_version = record.get("price_basis_version")
            row.benchmark_comparability_gate = record.get(
                "benchmark_comparability_gate"
            )
            row.comparison_eligibility = record.get("comparison_eligibility")
            session.add(row)
            session.commit()
            session.refresh(row)
            return _run_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist research run record run_id=%s",
            record["run_id"],
        )
        raise DataAccessError("Failed to persist research run record.") from exc


def get_research_run_record(run_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, run_id)
            if row is not None:
                return _run_row_to_dict(row)
    except Exception as exc:
        logger.exception("Failed to load research run from DB run_id=%s", run_id)
        raise DataAccessError("Failed to load research run.") from exc

    raise DataNotFoundError(f"Research run '{run_id}' was not found.")


def list_research_run_records(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ResearchRun)
                .order_by(desc(ResearchRun.created_at), desc(ResearchRun.run_id))
                .limit(limit)
            )
            return [
                _run_row_to_dict(row) for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list research runs from DB")
        raise DataAccessError("Failed to list research runs.") from exc
