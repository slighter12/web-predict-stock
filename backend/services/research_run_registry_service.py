from __future__ import annotations

import logging
from typing import Any

from ..domain.research_run_payload import build_research_run_payload
from ..errors import BacktestError
from ..repositories.research_run_repository import persist_research_run_record
from ..runtime.errors import research_run_error_code
from ..schemas.research_runs import (
    ResearchRunCreateRequest,
    ResearchRunResponse,
    ValidationSummary,
)
from ..strategy_service import build_price_basis_version, build_threshold_policy_version

logger = logging.getLogger(__name__)

COMPARISON_METADATA_ONLY = "comparison_metadata_only"


def _request_payload_from_model(request: ResearchRunCreateRequest) -> dict[str, Any]:
    return request.model_dump(mode="json")


def _request_payload_value(
    request: ResearchRunCreateRequest | None,
    request_payload: dict[str, Any] | None,
    field: str,
) -> Any:
    if request is not None:
        return getattr(request, field, None)
    if request_payload is None:
        return None
    return request_payload.get(field)


def _strategy_payload(
    request: ResearchRunCreateRequest | None, request_payload: dict[str, Any] | None
) -> Any:
    if request is not None:
        return request.strategy
    if request_payload is None:
        return None
    strategy = request_payload.get("strategy")
    if isinstance(strategy, dict):
        return strategy
    return None


def _strategy_value(strategy: Any, field: str) -> Any:
    if strategy is None:
        return None
    if isinstance(strategy, dict):
        return strategy.get(field)
    return getattr(strategy, field, None)


def _symbols_value(
    request: ResearchRunCreateRequest | None, request_payload: dict[str, Any] | None
) -> list[str]:
    symbols = _request_payload_value(request, request_payload, "symbols")
    if isinstance(symbols, list):
        return [str(symbol) for symbol in symbols]
    return []


def _build_registry_payload(
    *,
    run_id: str,
    request_id: str,
    status: str,
    request: ResearchRunCreateRequest | None = None,
    request_payload: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
    validation_outcome: dict[str, Any] | None = None,
    rejection_reason: str | None = None,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    threshold_policy_version: str | None = None,
    price_basis_version: str | None = None,
    benchmark_comparability_gate: bool | None = None,
    comparison_eligibility: str | None = None,
) -> dict[str, Any]:
    serialized_request = (
        _request_payload_from_model(request)
        if request is not None
        else request_payload
    )
    strategy = _strategy_payload(request, serialized_request)
    request_return_target = _request_payload_value(
        request, serialized_request, "return_target"
    )

    return build_research_run_payload(
        run_id=run_id,
        request_id=request_id,
        status=status,
        request_payload=serialized_request,
        runtime_context=runtime_context,
        strategy_type=_strategy_value(strategy, "type"),
        market=_request_payload_value(request, serialized_request, "market"),
        symbols=_symbols_value(request, serialized_request),
        allow_proactive_sells=_strategy_value(strategy, "allow_proactive_sells"),
        validation_outcome=validation_outcome,
        rejection_reason=rejection_reason,
        metrics=metrics,
        warnings=warnings,
        threshold_policy_version=threshold_policy_version
        if threshold_policy_version is not None
        else build_threshold_policy_version(request_return_target),
        price_basis_version=price_basis_version
        if price_basis_version is not None
        else build_price_basis_version(request_return_target),
        benchmark_comparability_gate=benchmark_comparability_gate,
        comparison_eligibility=comparison_eligibility,
    )


def record_success(
    *,
    run_id: str,
    request_id: str,
    request: ResearchRunCreateRequest,
    runtime_context: dict[str, Any],
    response: ResearchRunResponse,
    validation_summary: ValidationSummary | None,
    warnings: list[str],
) -> dict[str, Any]:
    logger.info("Recording succeeded research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="succeeded",
            request=request,
            runtime_context=runtime_context,
            validation_outcome=validation_summary.model_dump(mode="json")
            if validation_summary
            else None,
            metrics=response.metrics.model_dump(mode="json"),
            warnings=warnings,
            threshold_policy_version=response.threshold_policy_version,
            price_basis_version=response.price_basis_version,
            benchmark_comparability_gate=response.benchmark_comparability_gate,
            comparison_eligibility=response.comparison_eligibility,
        )
    )


def record_rejection(
    *,
    run_id: str,
    request_id: str,
    request: ResearchRunCreateRequest,
    runtime_context: dict[str, Any] | None,
    exc: BacktestError,
) -> dict[str, Any]:
    logger.info("Recording rejected research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="rejected",
            request=request,
            runtime_context=runtime_context,
            validation_outcome={"error_code": research_run_error_code(exc)},
            rejection_reason=str(exc),
            benchmark_comparability_gate=False,
            comparison_eligibility=COMPARISON_METADATA_ONLY,
        )
    )


def record_failure(
    *,
    run_id: str,
    request_id: str,
    request: ResearchRunCreateRequest,
    runtime_context: dict[str, Any] | None,
    exc: Exception,
) -> dict[str, Any]:
    logger.info("Recording failed research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="failed",
            request=request,
            runtime_context=runtime_context,
            validation_outcome={"error_code": "DATA_ACCESS_FAILED"},
            rejection_reason=str(exc),
            benchmark_comparability_gate=False,
            comparison_eligibility=COMPARISON_METADATA_ONLY,
        )
    )


def record_validation_failure(
    *,
    run_id: str,
    request_id: str,
    request_payload: dict[str, Any] | None,
    details: dict[str, Any],
) -> dict[str, Any]:
    logger.info("Recording validation failed research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="validation_failed",
            request_payload=request_payload,
            validation_outcome={
                "error_code": "VALIDATION_FAILED",
                "details": details,
            },
            rejection_reason="請檢查輸入內容。",
        )
    )


def record_unexpected_failure(
    *,
    run_id: str,
    request_id: str,
    rejection_reason: str,
    request: ResearchRunCreateRequest | None = None,
    request_payload: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("Recording unexpected failed research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="failed",
            request=request,
            request_payload=request_payload,
            runtime_context=runtime_context,
            validation_outcome={"error_code": "INTERNAL_SERVER_ERROR"},
            rejection_reason=rejection_reason,
        )
    )
