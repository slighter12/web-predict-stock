from __future__ import annotations

from typing import Any

from .runtime_bundle import build_version_pack_payload


def _strategy_value(strategy_context: Any, key: str) -> Any:
    if isinstance(strategy_context, dict):
        return strategy_context.get(key)
    return getattr(strategy_context, key, None)


def build_research_run_payload(
    *,
    run_id: str,
    request_id: str,
    status: str,
    request_payload: dict[str, Any] | None,
    runtime_context: dict[str, Any] | None = None,
    strategy_type: str | None = None,
    market: str | None = None,
    symbols: list[str] | None = None,
    allow_proactive_sells: bool | None = None,
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
) -> dict[str, Any]:
    runtime_context = runtime_context or {}
    strategy_context = runtime_context.get("strategy")
    effective_strategy = None
    if strategy_context is not None:
        effective_strategy = {
            "threshold": _strategy_value(strategy_context, "threshold"),
            "top_n": _strategy_value(strategy_context, "top_n"),
        }

    payload = {
        "run_id": run_id,
        "request_id": request_id,
        "status": status,
        "market": market,
        "symbols": symbols or [],
        "strategy_type": strategy_type,
        "runtime_mode": request_payload.get("runtime_mode")
        if request_payload
        else None,
        "default_bundle_version": runtime_context.get("default_bundle_version")
        if runtime_context
        else (
            request_payload.get("default_bundle_version") if request_payload else None
        ),
        "effective_strategy": effective_strategy,
        "allow_proactive_sells": allow_proactive_sells,
        "config_sources": runtime_context.get("config_sources"),
        "fallback_audit": runtime_context.get("fallback_audit"),
        "validation_outcome": validation_outcome,
        "rejection_reason": rejection_reason,
        "request_payload": request_payload,
        "metrics": metrics,
        "warnings": warnings or [],
        "tradability_state": tradability_state,
        "tradability_contract_version": tradability_contract_version,
        "capacity_screening_active": capacity_screening_active,
        "missing_feature_policy_state": missing_feature_policy_state,
        "corporate_event_state": corporate_event_state,
        "full_universe_count": full_universe_count,
        "execution_universe_count": execution_universe_count,
        "execution_universe_ratio": execution_universe_ratio,
        "liquidity_bucket_schema_version": liquidity_bucket_schema_version,
        "liquidity_bucket_coverages": liquidity_bucket_coverages or [],
        "stale_mark_days_with_open_positions": stale_mark_days_with_open_positions,
        "stale_risk_share": stale_risk_share,
        "monitor_profile_id": monitor_profile_id,
        "monitor_observation_status": monitor_observation_status,
        "microstructure_observations": microstructure_observations or [],
    }
    payload.update(
        build_version_pack_payload(
            {
                "threshold_policy_version": threshold_policy_version,
                "price_basis_version": price_basis_version,
                "benchmark_comparability_gate": benchmark_comparability_gate,
                "comparison_eligibility": comparison_eligibility,
                "investability_screening_active": investability_screening_active,
                "capacity_screening_version": capacity_screening_version,
                "adv_basis_version": adv_basis_version,
                "missing_feature_policy_version": missing_feature_policy_version,
                "execution_cost_model_version": execution_cost_model_version,
                "comparison_review_matrix_version": comparison_review_matrix_version,
                "scheduled_review_cadence": scheduled_review_cadence,
                "model_family": model_family,
                "training_output_contract_version": training_output_contract_version,
                "adoption_comparison_policy_version": adoption_comparison_policy_version,
                "split_policy_version": split_policy_version,
                "bootstrap_policy_version": bootstrap_policy_version,
                "ic_overlap_policy_version": ic_overlap_policy_version,
            }
        )
    )
    return payload
