from __future__ import annotations

import logging
from uuid import uuid4

from ..domain.research_run_payload import build_research_run_payload
from ..errors import BacktestError, DataAccessError
from ..repositories.research_run_repository import (
    get_research_run_record,
    list_research_run_records,
    persist_research_run_record,
)
from ..runtime.errors import research_run_error_code
from ..schemas.research_runs import (
    ResearchRunCreateRequest,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)
from ..strategy_service import (
    COMPARISON_ELIGIBILITY,
    build_price_basis_version,
    build_threshold_policy_version,
)
from .backtest_engine_service import execute_research_run

logger = logging.getLogger(__name__)


def _persist_registry_record(payload: dict) -> None:
    try:
        persist_research_run_record(payload)
    except DataAccessError:
        logger.exception(
            "Failed to persist research run record run_id=%s status=%s",
            payload.get("run_id"),
            payload.get("status"),
        )


def create_research_run(
    request: ResearchRunCreateRequest, request_id: str, run_id: str | None = None
) -> ResearchRunResponse:
    run_id = run_id or str(uuid4())
    threshold_policy_version = build_threshold_policy_version(request.return_target)
    price_basis_version = build_price_basis_version(request.return_target)
    runtime_context = None
    try:
        artifacts = execute_research_run(run_id=run_id, request=request)
        runtime_context = artifacts.runtime_context
        _persist_registry_record(
            build_research_run_payload(
                run_id=run_id,
                request_id=request_id,
                status="succeeded",
                request_payload=request.model_dump(mode="json"),
                runtime_context=runtime_context,
                strategy_type=artifacts.response.effective_strategy
                and request.strategy.type,
                market=request.market,
                symbols=request.symbols,
                allow_proactive_sells=request.strategy.allow_proactive_sells,
                validation_outcome=artifacts.validation_summary.model_dump(mode="json")
                if artifacts.validation_summary
                else None,
                metrics=artifacts.response.metrics.model_dump(mode="json"),
                warnings=artifacts.warnings,
                threshold_policy_version=threshold_policy_version,
                price_basis_version=price_basis_version,
                benchmark_comparability_gate=False,
                comparison_eligibility=COMPARISON_ELIGIBILITY,
            )
        )
        return artifacts.response
    except BacktestError as exc:
        _persist_registry_record(
            build_research_run_payload(
                run_id=run_id,
                request_id=request_id,
                status="rejected",
                request_payload=request.model_dump(mode="json"),
                runtime_context=runtime_context,
                strategy_type=request.strategy.type,
                market=request.market,
                symbols=request.symbols,
                allow_proactive_sells=request.strategy.allow_proactive_sells,
                validation_outcome={"error_code": research_run_error_code(exc)},
                rejection_reason=str(exc),
                threshold_policy_version=threshold_policy_version,
                price_basis_version=price_basis_version,
                benchmark_comparability_gate=False,
                comparison_eligibility=COMPARISON_ELIGIBILITY,
            )
        )
        raise
    except DataAccessError as exc:
        _persist_registry_record(
            build_research_run_payload(
                run_id=run_id,
                request_id=request_id,
                status="failed",
                request_payload=request.model_dump(mode="json"),
                runtime_context=runtime_context,
                strategy_type=request.strategy.type,
                market=request.market,
                symbols=request.symbols,
                allow_proactive_sells=request.strategy.allow_proactive_sells,
                validation_outcome={"error_code": "DATA_ACCESS_FAILED"},
                rejection_reason=str(exc),
                threshold_policy_version=threshold_policy_version,
                price_basis_version=price_basis_version,
                benchmark_comparability_gate=False,
                comparison_eligibility=COMPARISON_ELIGIBILITY,
            )
        )
        raise
    except Exception as exc:
        _persist_registry_record(
            build_research_run_payload(
                run_id=run_id,
                request_id=request_id,
                status="failed",
                request_payload=request.model_dump(mode="json"),
                runtime_context=runtime_context,
                strategy_type=request.strategy.type,
                market=request.market,
                symbols=request.symbols,
                allow_proactive_sells=request.strategy.allow_proactive_sells,
                validation_outcome={"error_code": "INTERNAL_SERVER_ERROR"},
                rejection_reason=str(exc),
                threshold_policy_version=threshold_policy_version,
                price_basis_version=price_basis_version,
                benchmark_comparability_gate=False,
                comparison_eligibility=COMPARISON_ELIGIBILITY,
            )
        )
        raise


def get_research_run(run_id: str) -> ResearchRunRecordResponse:
    return ResearchRunRecordResponse(**get_research_run_record(run_id))


def list_research_runs(limit: int = 20) -> list[ResearchRunRecordResponse]:
    return [
        ResearchRunRecordResponse(**item)
        for item in list_research_run_records(limit=limit)
    ]
