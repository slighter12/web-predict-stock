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
    investability_screening_active: bool | None = None,
    capacity_screening_active: bool | None = None,
    capacity_screening_version: str | None = None,
    adv_basis_version: str | None = None,
    missing_feature_policy_version: str | None = None,
    execution_cost_model_version: str | None = None,
    tradability_state: str | None = None,
    tradability_contract_version: str | None = None,
    missing_feature_policy_state: str | None = None,
    corporate_event_state: str | None = None,
    full_universe_count: int | None = None,
    execution_universe_count: int | None = None,
    execution_universe_ratio: float | None = None,
    liquidity_bucket_schema_version: str | None = None,
    liquidity_bucket_coverages: list[dict[str, Any]] | None = None,
    stale_mark_days_with_open_positions: int | None = None,
    stale_risk_share: float | None = None,
    monitor_profile_id: str | None = None,
    monitor_observation_status: str | None = None,
    microstructure_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    serialized_request = (
        _request_payload_from_model(request) if request is not None else request_payload
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
        investability_screening_active=investability_screening_active,
        capacity_screening_active=capacity_screening_active,
        capacity_screening_version=capacity_screening_version,
        adv_basis_version=adv_basis_version,
        missing_feature_policy_version=missing_feature_policy_version,
        execution_cost_model_version=execution_cost_model_version,
        tradability_state=tradability_state,
        tradability_contract_version=tradability_contract_version,
        missing_feature_policy_state=missing_feature_policy_state,
        corporate_event_state=corporate_event_state,
        full_universe_count=full_universe_count,
        execution_universe_count=execution_universe_count,
        execution_universe_ratio=execution_universe_ratio,
        liquidity_bucket_schema_version=liquidity_bucket_schema_version,
        liquidity_bucket_coverages=liquidity_bucket_coverages,
        stale_mark_days_with_open_positions=stale_mark_days_with_open_positions,
        stale_risk_share=stale_risk_share,
        monitor_profile_id=monitor_profile_id,
        monitor_observation_status=monitor_observation_status,
        microstructure_observations=microstructure_observations,
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
            investability_screening_active=response.investability_screening_active,
            capacity_screening_active=response.capacity_screening_active,
            capacity_screening_version=response.capacity_screening_version,
            adv_basis_version=response.adv_basis_version,
            missing_feature_policy_version=response.missing_feature_policy_version,
            execution_cost_model_version=response.execution_cost_model_version,
            tradability_state=response.tradability_state,
            tradability_contract_version=response.tradability_contract_version,
            missing_feature_policy_state=response.missing_feature_policy_state,
            corporate_event_state=response.corporate_event_state,
            full_universe_count=response.full_universe_count,
            execution_universe_count=response.execution_universe_count,
            execution_universe_ratio=response.execution_universe_ratio,
            liquidity_bucket_schema_version=response.liquidity_bucket_schema_version,
            liquidity_bucket_coverages=[
                item.model_dump(mode="json")
                for item in response.liquidity_bucket_coverages
            ],
            stale_mark_days_with_open_positions=response.stale_mark_days_with_open_positions,
            stale_risk_share=response.stale_risk_share,
            monitor_profile_id=runtime_context.get("p3_summary", {}).get(
                "monitor_profile_id"
            ),
            monitor_observation_status=response.monitor_observation_status,
            microstructure_observations=runtime_context.get("p3_summary", {}).get(
                "microstructure_observations",
                [],
            ),
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
