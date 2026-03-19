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
    }
    payload.update(
        build_version_pack_payload(
            {
                "threshold_policy_version": threshold_policy_version,
                "price_basis_version": price_basis_version,
                "benchmark_comparability_gate": benchmark_comparability_gate,
                "comparison_eligibility": comparison_eligibility,
            }
        )
    )
    return payload
