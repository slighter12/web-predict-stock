from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any, Iterable

STRICT_MODE = "strict_v1"
COHORT_2330 = "tw_2330_o2o_v1"
COHORT_ALL_ACTIVE = "tw_all_active_o2o_v1"
COHORT_IDS = (COHORT_2330, COHORT_ALL_ACTIVE)
MIN_EXECUTION_COVERAGE = 0.95

STRICT_FEATURES = [
    {"name": "ma", "window": 5, "source": "close", "shift": 1},
    {"name": "rsi", "window": 14, "source": "close", "shift": 1},
]
STRICT_MODEL_PARAMS = {"n_estimators": 200, "random_state": 42, "n_jobs": -1}
STRICT_MODEL = {"type": "extra_trees", "params": STRICT_MODEL_PARAMS}
STRICT_DIRECTION_MODEL = {
    "type": "extra_trees",
    "params": STRICT_MODEL_PARAMS,
    "positive_return_threshold": 0.0,
    "confirmation_probability_threshold": 0.5,
    "calibration_policy_version": "chronological_tail_20pct_min20_class5_v1",
    "confirmation_policy_version": (
        "regression_threshold_direction_probability_v1"
    ),
}
STRICT_STRATEGY = {
    "type": "research_v1",
    "threshold": None,
    "top_n": None,
    "allow_proactive_sells": True,
}
STRICT_EXECUTION = {"slippage": 0.001, "fees": 0.002}
STRICT_VALIDATION = {"method": "walk_forward", "splits": 3, "test_size": 0.2}
STRICT_BASELINES = ["buy_and_hold"]

_STRICT_DEFAULT_FIELDS = {
    "portfolio_aum": None,
    "monitor_profile_id": None,
    "factor_catalog_version": None,
    "scoring_factor_ids": [],
    "external_signal_policy_version": None,
    "cluster_snapshot_version": None,
    "peer_policy_version": None,
    "simulation_profile_id": None,
    "live_control_profile_id": None,
    "manual_confirmed": False,
    "adaptive_mode": "off",
    "adaptive_profile_id": None,
    "reward_definition_version": None,
    "state_definition_version": None,
    "rollout_control_version": None,
}


def _normalized_symbols(values: Iterable[Any]) -> list[str]:
    return [
        str(value).strip().upper()
        for value in values
        if str(value).strip()
    ]


def build_strict_request_payload(
    *,
    symbols: Iterable[Any],
    basis_date: date,
    cohort_id: str,
    full_universe_symbols: Iterable[Any],
) -> dict[str, Any]:
    if cohort_id not in COHORT_IDS:
        raise ValueError(f"Unknown prospective cohort '{cohort_id}'.")
    execution_symbols = sorted(set(_normalized_symbols(symbols)))
    full_symbols = sorted(set(_normalized_symbols(full_universe_symbols)))
    return {
        "runtime_mode": "vnext_spec_mode",
        "default_bundle_version": "research_spec_v1",
        "market": "TW",
        "symbols": execution_symbols,
        "date_range": {
            "start": (basis_date - timedelta(days=1096)).isoformat(),
            "end": basis_date.isoformat(),
        },
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": deepcopy(STRICT_FEATURES),
        "model": deepcopy(STRICT_MODEL),
        "direction_model": deepcopy(STRICT_DIRECTION_MODEL),
        "strategy": deepcopy(STRICT_STRATEGY),
        "execution": deepcopy(STRICT_EXECUTION),
        "validation": deepcopy(STRICT_VALIDATION),
        "baselines": deepcopy(STRICT_BASELINES),
        **deepcopy(_STRICT_DEFAULT_FIELDS),
        "execution_route": "research_only",
        "prospective_evidence": {
            "mode": STRICT_MODE,
            "cohort_id": cohort_id,
            "basis_date": basis_date.isoformat(),
            "full_universe_symbols": full_symbols,
        },
    }


def strict_recipe_issues(payload: dict[str, Any]) -> list[str]:
    evidence = payload.get("prospective_evidence")
    if not isinstance(evidence, dict) or evidence.get("mode") != STRICT_MODE:
        return ["missing_strict_evidence"]
    try:
        basis_date = date.fromisoformat(str(evidence.get("basis_date")))
    except ValueError:
        return ["invalid_basis_date"]
    cohort_id = evidence.get("cohort_id")
    symbols = payload.get("symbols")
    snapshot = evidence.get("full_universe_symbols")
    if (
        cohort_id not in COHORT_IDS
        or not isinstance(symbols, list)
        or not isinstance(snapshot, list)
    ):
        return ["invalid_universe_snapshot"]

    expected = build_strict_request_payload(
        symbols=symbols,
        basis_date=basis_date,
        cohort_id=cohort_id,
        full_universe_symbols=snapshot,
    )
    actual_evidence = dict(evidence)
    actual_evidence.pop("signal_frozen_at", None)
    actual = {**payload, "prospective_evidence": actual_evidence}
    issues: list[str] = []

    if (
        actual.get("market") != expected["market"]
        or actual.get("return_target") != expected["return_target"]
        or actual.get("horizon_days") != expected["horizon_days"]
    ):
        issues.append("strict_target_mismatch")
    if actual.get("execution_route") != expected["execution_route"]:
        issues.append("strict_execution_route_mismatch")
    if actual.get("date_range") != expected["date_range"]:
        issues.append("strict_date_range_recipe_mismatch")
    if (
        actual.get("runtime_mode") != expected["runtime_mode"]
        or actual.get("default_bundle_version")
        != expected["default_bundle_version"]
    ):
        issues.append("strict_runtime_recipe_mismatch")
    if actual.get("features") != expected["features"]:
        issues.append("strict_feature_recipe_mismatch")
    if (
        actual.get("model") != expected["model"]
        or actual.get("direction_model") != expected["direction_model"]
    ):
        issues.append("strict_model_recipe_mismatch")
    if actual.get("validation") != expected["validation"]:
        issues.append("strict_validation_recipe_mismatch")
    if (
        actual.get("execution") != expected["execution"]
        or actual.get("baselines") != expected["baselines"]
    ):
        issues.append("strict_cost_or_baseline_recipe_mismatch")
    if actual.get("strategy") != expected["strategy"]:
        issues.append("strict_strategy_recipe_mismatch")
    if any(
        actual.get(field) != expected[field]
        for field in _STRICT_DEFAULT_FIELDS
    ):
        issues.append("strict_extended_recipe_mismatch")

    normalized_symbols = _normalized_symbols(symbols)
    normalized_snapshot = _normalized_symbols(snapshot)
    if (
        symbols != normalized_symbols
        or snapshot != normalized_snapshot
        or len(normalized_symbols) != len(set(normalized_symbols))
        or len(normalized_snapshot) != len(set(normalized_snapshot))
        or normalized_symbols != sorted(normalized_symbols)
        or normalized_snapshot != sorted(normalized_snapshot)
        or not set(normalized_symbols).issubset(normalized_snapshot)
    ):
        issues.append("invalid_universe_snapshot")
    elif cohort_id == COHORT_2330:
        if normalized_symbols != ["2330"] or normalized_snapshot != ["2330"]:
            issues.append("strict_2330_universe_mismatch")
    return issues
