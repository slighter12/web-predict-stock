from __future__ import annotations

from typing import Any

VERSION_PACK_FIELDS = [
    "threshold_policy_version",
    "price_basis_version",
    "benchmark_comparability_gate",
    "comparison_eligibility",
    "investability_screening_active",
    "capacity_screening_version",
    "adv_basis_version",
    "missing_feature_policy_version",
    "execution_cost_model_version",
    "split_policy_version",
    "bootstrap_policy_version",
    "ic_overlap_policy_version",
]

GOVERNANCE_FIELDS = [
    "comparison_review_matrix_version",
    "scheduled_review_cadence",
    "model_family",
    "training_output_contract_version",
    "adoption_comparison_policy_version",
]

IMPLEMENTED_VERSION_FIELDS = {
    "threshold_policy_version",
    "price_basis_version",
    "benchmark_comparability_gate",
    "comparison_eligibility",
    "investability_screening_active",
    "capacity_screening_version",
    "adv_basis_version",
    "missing_feature_policy_version",
    "execution_cost_model_version",
    "split_policy_version",
    "bootstrap_policy_version",
    "ic_overlap_policy_version",
}


def build_version_pack_payload(values: dict[str, Any] | None = None) -> dict[str, Any]:
    values = values or {}
    payload: dict[str, Any] = {}
    for field in VERSION_PACK_FIELDS:
        payload[field] = values.get(field)
    payload["version_pack_status"] = {
        field: "implemented" if field in IMPLEMENTED_VERSION_FIELDS else "placeholder"
        for field in VERSION_PACK_FIELDS
    }
    for field in GOVERNANCE_FIELDS:
        payload[field] = values.get(field)
    return payload
