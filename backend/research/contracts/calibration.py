from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    Field,
    computed_field,
    confloat,
    conint,
    conlist,
    field_validator,
    model_validator,
)

from backend.research.contracts.runs import ComparisonCaveat, DateRange, FeatureSpec
from backend.research.policies.calibration import (
    CALIBRATION_CANDIDATE_GRID_POLICY_VERSION,
    CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
    CALIBRATION_DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT,
    CALIBRATION_DIRECTION_CALIBRATION_MIN_SAMPLES,
    CALIBRATION_DIRECTION_CALIBRATION_TAIL_FRACTION,
    CALIBRATION_DIRECTION_PROBABILITY_CUTOFF,
    CALIBRATION_EXECUTED_PRESET,
    CALIBRATION_FEE,
    CALIBRATION_DATA_SOURCE_POLICY_VERSION,
    CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION,
    CALIBRATION_FOLD_POLICY_VERSION,
    CALIBRATION_MARKET_DATE_AXIS_POLICY_VERSION,
    CALIBRATION_MAX_DATE_COUNT,
    CALIBRATION_MAX_FEATURES,
    CALIBRATION_MAX_SYMBOLS,
    CALIBRATION_POLICY_VERSION,
    CALIBRATION_REQUEST_BOUNDS_POLICY_VERSION,
    CALIBRATION_RESOURCE_POLICY_VERSION,
    CALIBRATION_SLIPPAGE,
    CALIBRATION_HORIZON_OUTCOME_POLICY_VERSION,
    CALIBRATION_MATCHED_BASELINE_POLICY_VERSION,
    CALIBRATION_REFERENCE_BASELINE_POLICY_VERSION,
    SUPPORTED_CALIBRATION_MODEL_FAMILIES,
    CALIBRATION_VOLATILITY_POLICY_VERSION,
)
from backend.shared.contracts.common import ModelType, RequestModel


CalibrationMatrixStatus = Literal["running", "succeeded", "failed"]
CalibrationEvaluationStatus = Literal["evaluated", "not_evaluated"]
CalibrationArtifactCompleteness = Literal["complete", "partial"]
CalibrationCandidateStatus = Literal["evaluated", "not_evaluated", "no_opinion"]


class CalibrationMatrixCreateRequest(RequestModel):
    market: Literal["TW"] = "TW"
    symbols: conlist(  # type: ignore[valid-type]
        str,
        min_length=1,
        max_length=CALIBRATION_MAX_SYMBOLS,
    )
    date_range: DateRange
    return_target: Literal["open_to_open"] = "open_to_open"
    horizon_days: Literal[5, 20] = 5
    features: conlist(  # type: ignore[valid-type]
        FeatureSpec,
        min_length=1,
        max_length=CALIBRATION_MAX_FEATURES,
    )
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
    def model_families_must_be_unique(
        cls, value: list[ModelType]
    ) -> list[ModelType]:
        if not value:
            raise ValueError("model_families must include at least one family")
        if len(value) != len(set(value)):
            raise ValueError("model_families must not contain duplicates")
        return value

    @field_validator("features")
    @classmethod
    def features_must_be_unique(cls, value: list[FeatureSpec]) -> list[FeatureSpec]:
        seen: set[tuple[str, int, str]] = set()
        for feature in value:
            key = (feature.name, feature.window, feature.source)
            if key in seen:
                raise ValueError(
                    "features must not contain duplicates with the same name, window, and source"
                )
            seen.add(key)
        return value

    @field_validator("date_range")
    @classmethod
    def date_range_must_fit_bounds(cls, value: DateRange) -> DateRange:
        date_count = (value.end - value.start).days + 1
        if date_count > CALIBRATION_MAX_DATE_COUNT:
            raise ValueError(
                "date_range must contain at most "
                f"{CALIBRATION_MAX_DATE_COUNT} inclusive calendar dates"
            )
        return value


class CalibrationSymbolExclusion(RequestModel):
    symbol: str
    reason: str
    excluded_row_count: conint(ge=0) = 0  # type: ignore[valid-type]


class CalibrationSymbolCoverage(RequestModel):
    symbol: str
    canonical_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    market_date_axis_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    missing_market_date_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    invalid_ohlcv_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    model_ready_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    excluded_canonical_row_count: conint(ge=0) = 0  # type: ignore[valid-type]


class CalibrationDatasetSummary(RequestModel):
    requested_symbol_count: conint(ge=1)  # type: ignore[valid-type]
    model_ready_symbol_count: conint(ge=0) = 0  # type: ignore[valid-type]
    model_ready_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    market_date_start: date | None = None
    market_date_end: date | None = None
    market_date_axis_policy_version: str = (
        CALIBRATION_MARKET_DATE_AXIS_POLICY_VERSION
    )
    feature_names: list[str] = Field(default_factory=list)
    exclusions: list[CalibrationSymbolExclusion] = Field(default_factory=list)
    symbol_coverage: list[CalibrationSymbolCoverage] = Field(default_factory=list)
    feature_continuity_policy_version: str = (
        CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION
    )


class CalibrationFoldSummary(RequestModel):
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


class CalibrationModelManifest(RequestModel):
    model_type: ModelType
    executed_preset: Literal["balanced"] = CALIBRATION_EXECUTED_PRESET
    presets: dict[str, dict[str, Any]]
    policy_version: str


class CalibrationModelAvailability(RequestModel):
    model_type: ModelType
    available: bool
    reason: str | None = None
    executed_preset: Literal["balanced"] = CALIBRATION_EXECUTED_PRESET
    evaluated_fold_count: conint(ge=0) = 0  # type: ignore[valid-type]


class CalibrationFoldMetrics(RequestModel):
    fold_number: conint(ge=1)  # type: ignore[valid-type]
    evaluation_status: CalibrationEvaluationStatus
    status_reason: str | None = None
    sample_count: conint(ge=0) = 0  # type: ignore[valid-type]
    rmse: confloat(ge=0) | None = None  # type: ignore[valid-type]
    mae: confloat(ge=0) | None = None  # type: ignore[valid-type]
    rank_ic: float | None = None
    linear_ic: float | None = None

    @model_validator(mode="after")
    def status_reason_must_explain_not_evaluated(self) -> "CalibrationFoldMetrics":
        if self.evaluation_status == "not_evaluated" and not self.status_reason:
            raise ValueError("not_evaluated fold metrics require status_reason")
        return self


class CalibrationCandidateManifest(RequestModel):
    candidate_id: str
    horizon_days: Literal[5, 20]
    return_target: Literal["open_to_open"] = "open_to_open"
    volatility_lookback: conint(ge=2)  # type: ignore[valid-type]
    multiplier: confloat(gt=0)  # type: ignore[valid-type]
    top_n: conint(ge=1)  # type: ignore[valid-type]
    volatility_estimator: Literal["sample_standard_deviation"] = (
        "sample_standard_deviation"
    )
    volatility_ddof: Literal[1] = 1
    volatility_requires_full_window: Literal[True] = True
    horizon_scaling: Literal["square_root"] = "square_root"
    probability_cutoff: confloat(ge=0, le=1) = (  # type: ignore[valid-type]
        CALIBRATION_DIRECTION_PROBABILITY_CUTOFF
    )
    probability_comparison: Literal["greater_or_equal"] = "greater_or_equal"
    grid_policy_version: str = CALIBRATION_CANDIDATE_GRID_POLICY_VERSION
    volatility_policy_version: str = CALIBRATION_VOLATILITY_POLICY_VERSION
    direction_gate_policy_version: str = CALIBRATION_DIRECTION_GATE_POLICY_VERSION
    matched_baseline_policy_version: str = CALIBRATION_MATCHED_BASELINE_POLICY_VERSION
    horizon_outcome_policy_version: str = CALIBRATION_HORIZON_OUTCOME_POLICY_VERSION
    matched_baseline_selection: str = (
        "ungated_score_top_n_on_action_dates"
    )
    equal_weighted: Literal[True] = True
    fee: confloat(ge=0) = CALIBRATION_FEE  # type: ignore[valid-type]
    slippage: confloat(ge=0) = CALIBRATION_SLIPPAGE  # type: ignore[valid-type]
    outcome_aggregation: Literal["equal_weight_by_signal_date_then_mean"] = (
        "equal_weight_by_signal_date_then_mean"
    )


class CalibrationCandidateEvaluationPolicy(RequestModel):
    direction_gate_policy_version: str = CALIBRATION_DIRECTION_GATE_POLICY_VERSION
    matched_baseline_policy_version: str = CALIBRATION_MATCHED_BASELINE_POLICY_VERSION
    reference_baseline_policy_version: str = CALIBRATION_REFERENCE_BASELINE_POLICY_VERSION
    probability_cutoff: confloat(ge=0, le=1) = CALIBRATION_DIRECTION_PROBABILITY_CUTOFF  # type: ignore[valid-type]
    calibration_tail_fraction: confloat(gt=0, lt=1) = CALIBRATION_DIRECTION_CALIBRATION_TAIL_FRACTION  # type: ignore[valid-type]
    minimum_sample_count: conint(ge=1) = CALIBRATION_DIRECTION_CALIBRATION_MIN_SAMPLES  # type: ignore[valid-type]
    minimum_class_support: conint(ge=1) = CALIBRATION_DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT  # type: ignore[valid-type]
    action_metric_aggregation: Literal["equal_weight_by_signal_date_then_mean"] = "equal_weight_by_signal_date_then_mean"


class CalibrationDirectionCalibrationEvidence(RequestModel):
    calibration_date_start: date | None = None
    calibration_date_end: date | None = None
    base_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    calibration_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    base_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    calibration_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    target_purge_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    base_class_counts: dict[str, conint(ge=0)] = Field(default_factory=dict)  # type: ignore[valid-type]
    calibration_class_counts: dict[str, conint(ge=0)] = Field(default_factory=dict)  # type: ignore[valid-type]


class CalibrationOutcomeMetrics(RequestModel):
    signal_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    participant_count: conint(ge=0) = 0  # type: ignore[valid-type]
    mean_gross_return: float | None = None
    mean_net_return: float | None = None


class CalibrationCandidateFoldResult(RequestModel):
    fold_number: conint(ge=1)  # type: ignore[valid-type]
    status: CalibrationCandidateStatus
    status_reason: str | None = None
    threshold_unavailable_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    eligible_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    eligible_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    gate_pass_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    gate_pass_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    gate_rejected_market_date_count: conint(ge=0) = 0  # type: ignore[valid-type]
    action_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    action_row_threshold_hit_count: conint(ge=0) = 0  # type: ignore[valid-type]
    action_row_threshold_hit_rate: confloat(ge=0, le=1) | None = None  # type: ignore[valid-type]
    mean_realized_excess_return: float | None = None
    candidate_outcomes: CalibrationOutcomeMetrics = Field(
        default_factory=CalibrationOutcomeMetrics
    )
    matched_baseline_outcomes: CalibrationOutcomeMetrics = Field(
        default_factory=CalibrationOutcomeMetrics
    )
    eligible_date_reference_baseline_outcomes: CalibrationOutcomeMetrics = Field(
        default_factory=CalibrationOutcomeMetrics
    )
    baseline_relative_mean_net_return: float | None = None
    direction_calibration: CalibrationDirectionCalibrationEvidence | None = None


class CalibrationCandidateResult(RequestModel):
    candidate_id: str
    status: CalibrationCandidateStatus
    status_reason: str | None = None
    evaluated_fold_count: conint(ge=0) = 0  # type: ignore[valid-type]
    no_opinion_fold_count: conint(ge=0) = 0  # type: ignore[valid-type]
    not_evaluated_fold_count: conint(ge=0) = 0  # type: ignore[valid-type]
    folds: list[CalibrationCandidateFoldResult] = Field(default_factory=list)


class CalibrationModelResult(RequestModel):
    model_type: ModelType
    availability: CalibrationModelAvailability
    folds: list[CalibrationFoldMetrics] = Field(default_factory=list)
    candidate_results: list[CalibrationCandidateResult] = Field(default_factory=list)


class CalibrationResourceEvidence(RequestModel):
    policy_version: str = CALIBRATION_RESOURCE_POLICY_VERSION
    request_bounds_policy_version: str = CALIBRATION_REQUEST_BOUNDS_POLICY_VERSION
    data_source_policy_version: str = CALIBRATION_DATA_SOURCE_POLICY_VERSION
    wall_clock_seconds: confloat(ge=0)  # type: ignore[valid-type]
    cpu_seconds: confloat(ge=0)  # type: ignore[valid-type]
    peak_rss_bytes: conint(ge=0) | None = None  # type: ignore[valid-type]
    model_ready_row_count: conint(ge=0) = 0  # type: ignore[valid-type]
    feature_count: conint(ge=0) = 0  # type: ignore[valid-type]
    fold_count: conint(ge=0) = 0  # type: ignore[valid-type]
    model_fit_count: conint(ge=0) = 0  # type: ignore[valid-type]
    regression_fit_attempt_count: conint(ge=0) = 0  # type: ignore[valid-type]
    direction_gate_fit_attempt_count: conint(ge=0) = 0  # type: ignore[valid-type]
    deduplicated_market_date_row_count: conint(ge=0) = 0  # type: ignore[valid-type]


class CalibrationArtifactEvidence(RequestModel):
    completeness: CalibrationArtifactCompleteness = "complete"
    policy_version: str = CALIBRATION_POLICY_VERSION
    present_artifacts: list[str] = Field(default_factory=list)
    missing_artifacts: list[str] = Field(default_factory=list)


class CalibrationEvaluation(RequestModel):
    status: CalibrationEvaluationStatus
    status_reason: str | None = None
    fold_policy_version: str = CALIBRATION_FOLD_POLICY_VERSION
    model_results: list[CalibrationModelResult] = Field(default_factory=list)
    candidate_manifest: list[CalibrationCandidateManifest] = Field(default_factory=list)
    candidate_evaluation_policy: CalibrationCandidateEvaluationPolicy = Field(
        default_factory=CalibrationCandidateEvaluationPolicy
    )
    artifact_evidence: CalibrationArtifactEvidence
    resource_evidence: CalibrationResourceEvidence

    @model_validator(mode="before")
    @classmethod
    def discard_derived_model_availability(cls, value: Any) -> Any:
        if isinstance(value, dict) and "model_availability" in value:
            value = dict(value)
            value.pop("model_availability", None)
        return value

    @computed_field
    @property
    def model_availability(self) -> list[CalibrationModelAvailability]:
        """Expose availability as a read-only projection of model results."""
        return [result.availability for result in self.model_results]


class CalibrationMatrixResponse(RequestModel):
    matrix_id: str
    request_id: str
    feature_registry_version: str | None = None
    status: CalibrationMatrixStatus
    request: CalibrationMatrixCreateRequest
    dataset: CalibrationDatasetSummary
    folds: list[CalibrationFoldSummary] = Field(default_factory=list)
    model_manifest: list[CalibrationModelManifest] = Field(default_factory=list)
    comparison_caveats: list[ComparisonCaveat] = Field(default_factory=list)
    evaluation: CalibrationEvaluation
    created_at: datetime
