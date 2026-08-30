from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, conint, conlist, field_validator

from backend.research.contracts.calibration import (
    CalibrationCandidateFoldResult,
    CalibrationDatasetSummary,
    CalibrationResourceEvidence,
)
from backend.research.contracts.runs import ComparisonCaveat, DateRange
from backend.research.policies.calibration import (
    CALIBRATION_MAX_DATE_COUNT,
    CALIBRATION_MAX_SYMBOLS,
    SUPPORTED_CALIBRATION_MODEL_FAMILIES,
    capacity_presets_for,
)
from backend.shared.contracts.common import ModelType, RequestModel


MethodSelectionStatus = Literal["succeeded"]
MethodCandidateStatus = Literal["evaluated", "no_opinion", "not_evaluated"]


class MethodSelectionMatrixCreateRequest(RequestModel):
    market: Literal["TW"] = "TW"
    symbols: conlist(str, min_length=1, max_length=CALIBRATION_MAX_SYMBOLS)  # type: ignore[valid-type]
    date_range: DateRange
    horizon_days: Literal[5, 20] = 5
    model_families: list[ModelType] = Field(
        default_factory=lambda: list(SUPPORTED_CALIBRATION_MODEL_FAMILIES)
    )

    @field_validator("symbols")
    @classmethod
    def symbols_must_be_unique(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in value]
        if any(not symbol for symbol in normalized):
            raise ValueError("symbols must not contain blank values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols must not contain duplicates")
        return normalized

    @field_validator("model_families")
    @classmethod
    def model_families_must_be_unique(cls, value: list[ModelType]) -> list[ModelType]:
        if not value:
            raise ValueError("model_families must include at least one family")
        if len(value) != len(set(value)):
            raise ValueError("model_families must not contain duplicates")
        return value

    @field_validator("date_range")
    @classmethod
    def date_range_must_fit_bounds(cls, value: DateRange) -> DateRange:
        if (value.end - value.start).days + 1 > CALIBRATION_MAX_DATE_COUNT:
            raise ValueError(
                f"date_range must contain at most {CALIBRATION_MAX_DATE_COUNT} inclusive calendar dates"
            )
        return value


class MethodSelectionFeatureSetManifest(RequestModel):
    feature_set_id: str
    included_feature_families: list[str]
    removed_feature_family: str | None = None
    baseline_feature_names: list[str]
    feature_names: list[str]


class MethodCandidateManifest(RequestModel):
    candidate_id: str
    phase: Literal["feature_screening", "parameter_search"]
    feature_set_id: str
    feature_families: list[str]
    horizon_days: Literal[5, 20]
    model_type: ModelType
    capacity_preset: Literal["conservative", "balanced", "flexible"]
    model_params: dict[str, Any]
    volatility_lookback: conint(ge=2)  # type: ignore[valid-type]
    multiplier: float
    top_n: conint(ge=1)  # type: ignore[valid-type]
    threshold_policy_version: str
    direction_gate_policy_version: str
    matched_baseline_policy_version: str


class MethodSelectionFoldBoundary(RequestModel):
    number: conint(ge=1)  # type: ignore[valid-type]
    train_market_date_count: conint(ge=0)  # type: ignore[valid-type]
    train_date_start: date | None = None
    train_date_end: date | None = None
    purge_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    purge_date_start: date | None = None
    purge_date_end: date | None = None
    holdout_market_date_count: conint(ge=0)  # type: ignore[valid-type]
    holdout_date_start: date | None = None
    holdout_date_end: date | None = None
    train_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    target_purge_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    holdout_row_count: conint(ge=0) = 0  # type: ignore[valid-type]


class MethodCandidateSummary(RequestModel):
    candidate_id: str
    status: MethodCandidateStatus
    status_reason: str | None = None
    fold_results: list[CalibrationCandidateFoldResult] = Field(default_factory=list)
    action_row_threshold_hit_rate: float | None = None
    mean_realized_excess_return: float | None = None
    action_row_stability: float | None = None
    baseline_relative_mean_net_return: float | None = None
    action_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    action_row_threshold_hit_count: conint(ge=0) = 0  # type: ignore[valid-type]
    rank: conint(ge=1) | None = None  # type: ignore[valid-type]
    rejection_reason: str | None = None
    semantic_tie: bool = False
    tied_candidate_ids: list[str] = Field(default_factory=list)
    deterministic_tie_break: str | None = None


class MethodSelectionComparabilityEvidence(RequestModel):
    policy_version: str
    selection_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    common_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    common_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    feature_set_complete_case_row_counts: dict[str, conint(ge=0)] = Field(  # type: ignore[valid-type]
        default_factory=dict
    )
    common_policy_rows_lost_by_feature_set: dict[str, conint(ge=0)] = Field(  # type: ignore[valid-type]
        default_factory=dict
    )


class MethodSelectionResourceEvidence(CalibrationResourceEvidence):
    maximum_regression_fit_count: conint(ge=0) = 0  # type: ignore[valid-type]
    maximum_direction_gate_fit_count: conint(ge=0) = 0  # type: ignore[valid-type]


class MethodSelectionModelAvailability(RequestModel):
    model_type: ModelType
    available: bool
    reason: str | None = None
    evaluated_group_fold_count: conint(ge=0) = 0  # type: ignore[valid-type]


class MethodSelectionOuterFoldResult(RequestModel):
    outer_fold: MethodSelectionFoldBoundary
    inner_folds: list[MethodSelectionFoldBoundary]
    phase_a_summaries: list[MethodCandidateSummary]
    phase_a_selected_candidate_id: str | None = None
    phase_b_summaries: list[MethodCandidateSummary]
    selected_candidate_id: str | None = None
    selection_reason: str | None = None
    outer_result: CalibrationCandidateFoldResult | None = None


class MethodSelectionMatrixResponse(RequestModel):
    matrix_id: str
    request_id: str
    status: MethodSelectionStatus = "succeeded"
    request: MethodSelectionMatrixCreateRequest
    feature_registry_version: str
    dataset: CalibrationDatasetSummary
    final_holdout_policy_version: str
    final_holdout_market_dates: list[date]
    fold_policy_version: str
    policy_version: str
    feature_ablation_policy_version: str
    ranking_policy_version: str
    screening_policy_version: str
    outer_stability_policy_version: str
    feature_sets: list[MethodSelectionFeatureSetManifest]
    phase_a_candidate_manifests: list[MethodCandidateManifest]
    phase_b_candidate_manifests: list[MethodCandidateManifest]
    outer_folds: list[MethodSelectionOuterFoldResult]
    outer_candidate_summaries: list[MethodCandidateSummary] = Field(
        default_factory=list
    )
    comparison_caveats: list[ComparisonCaveat] = Field(default_factory=list)
    resource_evidence: MethodSelectionResourceEvidence
    model_availability: list[MethodSelectionModelAvailability] = Field(
        default_factory=list
    )
    comparability_evidence: MethodSelectionComparabilityEvidence
    created_at: datetime
