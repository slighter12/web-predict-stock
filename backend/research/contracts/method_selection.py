from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, conint, conlist, field_validator, model_validator

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
    METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION,
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
    final_inner_candidate_count: conint(ge=0) = 0  # type: ignore[valid-type]
    final_inner_execution_count: conint(ge=0) = 0  # type: ignore[valid-type]
    final_inner_reuse_count: conint(ge=0) = 0  # type: ignore[valid-type]
    final_holdout_execution_count: conint(ge=0) = 0  # type: ignore[valid-type]
    final_holdout_reuse_count: conint(ge=0) = 0  # type: ignore[valid-type]


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


class MethodSelectionFinalHoldoutResult(RequestModel):
    shortlisted_candidate_id: str
    final_candidate_id: str | None = None
    final_candidate_manifest: MethodCandidateManifest | None = None
    final_inner_folds: list[MethodSelectionFoldBoundary] = Field(
        default_factory=list
    )
    final_inner_summaries: list[MethodCandidateSummary] = Field(
        default_factory=list
    )
    final_inner_selection_reuse_mode: Literal[
        "computed", "deterministic_reused"
    ] = "computed"
    final_holdout_evaluation_reuse_mode: Literal[
        "computed", "deterministic_reused"
    ] = "computed"
    final_inner_selected_candidate_id: str | None = None
    final_holdout_policy_version: str
    final_holdout_market_dates: list[date] = Field(default_factory=list)
    final_holdout_boundary: MethodSelectionFoldBoundary
    final_holdout_maturity_policy_version: str = (
        METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION
    )
    final_holdout_maturity_date: date | None = None
    final_holdout_maturity_buffer_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    final_holdout_evaluation: CalibrationCandidateFoldResult | None = None
    status: Literal["promoted", "no_opinion", "not_evaluated"]
    status_reason: str | None = None
    promoted_research_run_id: str | None = None
    same_final_configuration: bool = False
    final_configuration_group_id: str | None = None
    duplicate_configuration_run_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def promoted_result_has_complete_artifacts(
        self,
    ) -> "MethodSelectionFinalHoldoutResult":
        if self.status == "promoted":
            if not self.promoted_research_run_id:
                raise ValueError("promoted final results require a Research Run ID")
            if self.final_candidate_manifest is None:
                raise ValueError("promoted final results require a candidate manifest")
            if self.final_holdout_evaluation is None:
                raise ValueError(
                    "promoted final results require final Holdout evaluation evidence"
                )
        elif self.promoted_research_run_id is not None:
            raise ValueError(
                "non-promoted final results must not reference a Research Run"
            )
        if self.same_final_configuration and not self.final_configuration_group_id:
            raise ValueError(
                "duplicate final configurations require a configuration group ID"
            )
        if not self.same_final_configuration and self.duplicate_configuration_run_ids:
            raise ValueError(
                "unique final configurations must not list duplicate Research Runs"
            )
        return self


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
    final_inner_candidate_manifests: list[MethodCandidateManifest] = Field(
        default_factory=list
    )
    final_holdout_maturity_policy_version: str = (
        METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION
    )
    final_holdout_maturity_date: date | None = None
    final_holdout_maturity_buffer_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    outer_folds: list[MethodSelectionOuterFoldResult]
    outer_candidate_summaries: list[MethodCandidateSummary] = Field(
        default_factory=list
    )
    shortlist: list[MethodCandidateSummary] = Field(
        default_factory=list, max_length=3
    )
    final_holdout_results: list[MethodSelectionFinalHoldoutResult] = Field(
        default_factory=list, max_length=3
    )
    promoted_research_run_ids: list[str] = Field(
        default_factory=list, max_length=3
    )
    comparison_caveats: list[ComparisonCaveat] = Field(default_factory=list)
    resource_evidence: MethodSelectionResourceEvidence
    model_availability: list[MethodSelectionModelAvailability] = Field(
        default_factory=list
    )
    comparability_evidence: MethodSelectionComparabilityEvidence
    created_at: datetime

    @model_validator(mode="after")
    def promoted_runs_match_final_results(
        self,
    ) -> "MethodSelectionMatrixResponse":
        result_run_ids = [
            item.promoted_research_run_id
            for item in self.final_holdout_results
            if item.promoted_research_run_id is not None
        ]
        if len(self.promoted_research_run_ids) != len(
            set(self.promoted_research_run_ids)
        ):
            raise ValueError("promoted Research Run IDs must be unique")
        if len(result_run_ids) != len(set(result_run_ids)):
            raise ValueError(
                "each promoted final result must reference a unique Research Run"
            )
        if set(self.promoted_research_run_ids) != set(result_run_ids):
            raise ValueError(
                "promoted Research Run IDs must match promoted final results"
            )
        for result in self.final_holdout_results:
            if result.final_holdout_policy_version != self.final_holdout_policy_version:
                raise ValueError(
                    "final results must retain the Matrix Holdout policy version"
                )
            if result.final_holdout_market_dates != self.final_holdout_market_dates:
                raise ValueError(
                    "final results must retain the Matrix Holdout Market Dates"
                )
            if (
                result.final_holdout_maturity_policy_version
                != self.final_holdout_maturity_policy_version
            ):
                raise ValueError(
                    "final results must retain the Matrix Holdout maturity policy version"
                )
            if result.final_holdout_maturity_date != self.final_holdout_maturity_date:
                raise ValueError(
                    "final results must retain the Matrix Holdout maturity date"
                )
            if (
                result.final_holdout_maturity_buffer_market_date_count
                != self.final_holdout_maturity_buffer_market_date_count
            ):
                raise ValueError(
                    "final results must retain the Matrix Holdout maturity buffer evidence"
                )
        shortlist_ids = [item.candidate_id for item in self.shortlist]
        result_ids = [item.shortlisted_candidate_id for item in self.final_holdout_results]
        if result_ids != shortlist_ids:
            raise ValueError(
                "final Holdout results must retain one ordered result per shortlist entry"
            )
        return self
