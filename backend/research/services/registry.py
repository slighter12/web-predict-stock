from __future__ import annotations

import logging
from typing import Any

from backend.shared.analytics import models as model_service
from backend.research.domain.run_payload import build_research_run_payload
from backend.platform.errors import BacktestError
from backend.research.repositories.runs import persist_research_run_record
from backend.platform.http.errors import research_run_error_code
from backend.research.contracts.runs import (
    ResearchRunCreateRequest,
    ResearchRunResponse,
    ValidationSummary,
)
from backend.shared.analytics.strategy import (
    ADOPTION_COMPARISON_POLICY_VERSION,
    BOOTSTRAP_POLICY_VERSION,
    COMPARISON_ELIGIBILITY,
    COMPARISON_REVIEW_MATRIX_VERSION,
    IC_OVERLAP_POLICY_VERSION,
    SCHEDULED_REVIEW_CADENCE,
    build_price_basis_version,
    build_split_policy_version,
    build_threshold_policy_version,
)

logger = logging.getLogger(__name__)


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


def _model_payload(
    request: ResearchRunCreateRequest | None, request_payload: dict[str, Any] | None
) -> Any:
    if request is not None:
        return request.model
    if request_payload is None:
        return None
    model = request_payload.get("model")
    if isinstance(model, dict):
        return model
    return None


def _strategy_value(strategy: Any, field: str) -> Any:
    if strategy is None:
        return None
    if isinstance(strategy, dict):
        return strategy.get(field)
    return getattr(strategy, field, None)


def _model_value(model: Any, field: str) -> Any:
    if model is None:
        return None
    if isinstance(model, dict):
        return model.get(field)
    return getattr(model, field, None)


def _validation_payload(
    request: ResearchRunCreateRequest | None, request_payload: dict[str, Any] | None
) -> Any:
    if request is not None:
        return request.validation
    if request_payload is None:
        return None
    validation = request_payload.get("validation")
    if isinstance(validation, dict):
        return validation
    return None


def _safe_model_family(model_type: str) -> str | None:
    try:
        return model_service.build_model_family(model_type)
    except ValueError:
        return None


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
    comparison_review_matrix_version: str | None = None,
    scheduled_review_cadence: str | None = None,
    model_family: str | None = None,
    training_output_contract_version: str | None = None,
    adoption_comparison_policy_version: str | None = None,
    split_policy_version: str | None = None,
    bootstrap_policy_version: str | None = None,
    ic_overlap_policy_version: str | None = None,
    factor_catalog_version: str | None = None,
    scoring_factor_ids: list[str] | None = None,
    external_signal_policy_version: str | None = None,
    external_lineage_version: str | None = None,
    cluster_snapshot_version: str | None = None,
    peer_policy_version: str | None = None,
    peer_comparison_policy_version: str | None = None,
    execution_route: str | None = None,
    simulation_profile_id: str | None = None,
    simulation_adapter_version: str | None = None,
    live_control_profile_id: str | None = None,
    live_control_version: str | None = None,
    adaptive_mode: str | None = None,
    adaptive_profile_id: str | None = None,
    adaptive_contract_version: str | None = None,
    reward_definition_version: str | None = None,
    state_definition_version: str | None = None,
    rollout_control_version: str | None = None,
) -> dict[str, Any]:
    serialized_request = (
        _request_payload_from_model(request) if request is not None else request_payload
    )
    strategy = _strategy_payload(request, serialized_request)
    model = _model_payload(request, serialized_request)
    validation = _validation_payload(request, serialized_request)
    request_return_target = _request_payload_value(
        request, serialized_request, "return_target"
    )
    model_type = str(_model_value(model, "type") or "xgboost")
    validation_method = (
        validation.get("method")
        if isinstance(validation, dict)
        else getattr(validation, "method", None)
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
        comparison_review_matrix_version=(
            comparison_review_matrix_version or COMPARISON_REVIEW_MATRIX_VERSION
        ),
        scheduled_review_cadence=scheduled_review_cadence or SCHEDULED_REVIEW_CADENCE,
        model_family=model_family or _safe_model_family(model_type),
        training_output_contract_version=(
            training_output_contract_version
            or model_service.TRAINING_OUTPUT_CONTRACT_VERSION
        ),
        adoption_comparison_policy_version=(
            adoption_comparison_policy_version or ADOPTION_COMPARISON_POLICY_VERSION
        ),
        split_policy_version=split_policy_version
        or build_split_policy_version(validation_method),
        bootstrap_policy_version=bootstrap_policy_version or BOOTSTRAP_POLICY_VERSION,
        ic_overlap_policy_version=ic_overlap_policy_version
        or IC_OVERLAP_POLICY_VERSION,
        factor_catalog_version=factor_catalog_version
        if factor_catalog_version is not None
        else _request_payload_value(
            request, serialized_request, "factor_catalog_version"
        ),
        scoring_factor_ids=scoring_factor_ids
        if scoring_factor_ids is not None
        else _request_payload_value(request, serialized_request, "scoring_factor_ids"),
        external_signal_policy_version=external_signal_policy_version
        if external_signal_policy_version is not None
        else _request_payload_value(
            request, serialized_request, "external_signal_policy_version"
        ),
        external_lineage_version=external_lineage_version,
        cluster_snapshot_version=cluster_snapshot_version
        if cluster_snapshot_version is not None
        else _request_payload_value(
            request, serialized_request, "cluster_snapshot_version"
        ),
        peer_policy_version=peer_policy_version
        if peer_policy_version is not None
        else _request_payload_value(request, serialized_request, "peer_policy_version"),
        peer_comparison_policy_version=peer_comparison_policy_version,
        execution_route=execution_route
        if execution_route is not None
        else _request_payload_value(request, serialized_request, "execution_route"),
        simulation_profile_id=simulation_profile_id
        if simulation_profile_id is not None
        else _request_payload_value(
            request, serialized_request, "simulation_profile_id"
        ),
        simulation_adapter_version=simulation_adapter_version,
        live_control_profile_id=live_control_profile_id
        if live_control_profile_id is not None
        else _request_payload_value(
            request, serialized_request, "live_control_profile_id"
        ),
        live_control_version=live_control_version,
        adaptive_mode=adaptive_mode
        if adaptive_mode is not None
        else _request_payload_value(request, serialized_request, "adaptive_mode"),
        adaptive_profile_id=adaptive_profile_id
        if adaptive_profile_id is not None
        else _request_payload_value(request, serialized_request, "adaptive_profile_id"),
        adaptive_contract_version=adaptive_contract_version,
        reward_definition_version=reward_definition_version
        if reward_definition_version is not None
        else _request_payload_value(
            request, serialized_request, "reward_definition_version"
        ),
        state_definition_version=state_definition_version
        if state_definition_version is not None
        else _request_payload_value(
            request, serialized_request, "state_definition_version"
        ),
        rollout_control_version=rollout_control_version
        if rollout_control_version is not None
        else _request_payload_value(
            request, serialized_request, "rollout_control_version"
        ),
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
            comparison_review_matrix_version=response.comparison_review_matrix_version,
            scheduled_review_cadence=response.scheduled_review_cadence,
            model_family=response.model_family,
            training_output_contract_version=response.training_output_contract_version,
            adoption_comparison_policy_version=(
                response.adoption_comparison_policy_version
            ),
            split_policy_version=response.split_policy_version,
            bootstrap_policy_version=response.bootstrap_policy_version,
            ic_overlap_policy_version=response.ic_overlap_policy_version,
            factor_catalog_version=response.factor_catalog_version,
            scoring_factor_ids=response.scoring_factor_ids,
            external_signal_policy_version=response.external_signal_policy_version,
            external_lineage_version=response.external_lineage_version,
            cluster_snapshot_version=response.cluster_snapshot_version,
            peer_policy_version=response.peer_policy_version,
            peer_comparison_policy_version=response.peer_comparison_policy_version,
            execution_route=response.execution_route,
            simulation_profile_id=response.simulation_profile_id,
            simulation_adapter_version=response.simulation_adapter_version,
            live_control_profile_id=response.live_control_profile_id,
            live_control_version=response.live_control_version,
            adaptive_mode=response.adaptive_mode,
            adaptive_profile_id=response.adaptive_profile_id,
            adaptive_contract_version=response.adaptive_contract_version,
            reward_definition_version=response.reward_definition_version,
            state_definition_version=response.state_definition_version,
            rollout_control_version=response.rollout_control_version,
        )
    )


def record_started(
    *,
    run_id: str,
    request_id: str,
    request: ResearchRunCreateRequest,
) -> dict[str, Any]:
    logger.info("Recording started research run run_id=%s", run_id)
    return persist_research_run_record(
        _build_registry_payload(
            run_id=run_id,
            request_id=request_id,
            status="running",
            request=request,
            benchmark_comparability_gate=False,
            comparison_eligibility=COMPARISON_ELIGIBILITY,
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
            comparison_eligibility=COMPARISON_ELIGIBILITY,
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
            comparison_eligibility=COMPARISON_ELIGIBILITY,
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
