from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    confloat,
    conint,
    conlist,
    field_validator,
    model_validator,
)

from backend.shared.contracts.common import (
    AdaptiveMode,
    BaselineName,
    DefaultBundleVersion,
    ExecutionRoute,
    FeatureName,
    MarketCode,
    ModelType,
    PriceSource,
    RequestModel,
    ResearchMonitorProfileId,
    ReturnTarget,
    RunStatus,
    RuntimeMode,
    StrategyType,
    ValidationMethod,
)
from backend.research.contracts.artifacts import (
    ArtifactCompleteness,
    ReviewArtifactName,
)
from backend.research.policies.prospective import (
    STRICT_MODE,
    strict_recipe_issues,
)
from .runtime_metadata import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    FoundationMetadataMixin,
    GovernanceMetadataMixin,
    P3SummaryMixin,
    VersionPackMixin,
)


class DateRange(RequestModel):
    start: date = Field(..., description="Inclusive start date.")
    end: date = Field(..., description="Inclusive end date.")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, value: date, info: ValidationInfo) -> date:
        start = info.data.get("start")
        if start and value < start:
            raise ValueError("end must be on or after start")
        return value


class FeatureSpec(RequestModel):
    name: FeatureName
    window: conint(ge=1)  # type: ignore[valid-type]
    source: PriceSource = "close"
    shift: conint(ge=1) = 1  # type: ignore[valid-type]


class FeatureDefinition(BaseModel):
    name: str
    label: str
    description: str
    default_window: conint(ge=1)  # type: ignore[valid-type]
    allowed_sources: List[PriceSource] = Field(default_factory=list)


class FeatureRegistryResponse(BaseModel):
    version: str
    features: List[FeatureDefinition] = Field(default_factory=list)


class ModelConfig(RequestModel):
    type: ModelType = Field(default="extra_trees", description="Model identifier.")
    params: Dict[str, object] = Field(default_factory=dict)


class DirectionModelConfig(ModelConfig):
    positive_return_threshold: float = 0.0
    confirmation_probability_threshold: confloat(ge=0, le=1) = 0.5  # type: ignore[valid-type]
    calibration_policy_version: Literal[
        "chronological_tail_20pct_min20_class5_v1"
    ] = "chronological_tail_20pct_min20_class5_v1"
    confirmation_policy_version: Literal[
        "regression_threshold_direction_probability_v1"
    ] = "regression_threshold_direction_probability_v1"


class StrategyConfig(RequestModel):
    type: StrategyType = Field(
        default="research_v1", description="Strategy identifier."
    )
    threshold: Optional[confloat(ge=0)] = None  # type: ignore[valid-type]
    top_n: Optional[conint(ge=1)] = None  # type: ignore[valid-type]
    allow_proactive_sells: bool = True


class ExecutionConfig(RequestModel):
    slippage: confloat(ge=0) = 0.0  # type: ignore[valid-type]
    fees: confloat(ge=0) = 0.0  # type: ignore[valid-type]


class ValidationConfig(RequestModel):
    method: ValidationMethod = "walk_forward"
    splits: conint(ge=1) = 3  # type: ignore[valid-type]
    test_size: confloat(gt=0, lt=1) = 0.2  # type: ignore[valid-type]


ProspectiveEvidenceMode = Literal["strict_v1"]
ProspectiveEvidenceCohortId = Literal[
    "tw_2330_o2o_v1",
    "tw_all_active_o2o_v1",
]


class ProspectiveEvidenceConfig(RequestModel):
    mode: ProspectiveEvidenceMode = STRICT_MODE
    cohort_id: ProspectiveEvidenceCohortId
    basis_date: date
    full_universe_symbols: conlist(str, min_length=1)  # type: ignore[valid-type]

    @field_validator("full_universe_symbols")
    @classmethod
    def full_universe_symbols_must_be_unique(cls, value: List[str]) -> List[str]:
        normalized = [symbol.strip() for symbol in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("full_universe_symbols must not contain duplicates")
        return normalized


class ResearchRunCreateRequest(RequestModel):
    runtime_mode: RuntimeMode = "runtime_compatibility_mode"
    default_bundle_version: Optional[DefaultBundleVersion] = None
    market: MarketCode = Field(..., description="Market code.")
    symbols: conlist(str, min_length=1)  # type: ignore[valid-type]
    date_range: DateRange
    return_target: ReturnTarget = "open_to_open"
    horizon_days: conint(ge=1) = 1  # type: ignore[valid-type]
    features: List[FeatureSpec]
    model: ModelConfig = Field(default_factory=ModelConfig)
    direction_model: Optional[DirectionModelConfig] = None
    strategy: StrategyConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    validation: Optional[ValidationConfig] = None
    baselines: List[BaselineName] = Field(default_factory=list)
    portfolio_aum: Optional[confloat(gt=0)] = None  # type: ignore[valid-type]
    monitor_profile_id: Optional[ResearchMonitorProfileId] = None
    factor_catalog_version: Optional[str] = None
    scoring_factor_ids: List[str] = Field(default_factory=list)
    external_signal_policy_version: Optional[str] = None
    cluster_snapshot_version: Optional[str] = None
    peer_policy_version: Optional[str] = None
    execution_route: ExecutionRoute = "research_only"
    simulation_profile_id: Optional[str] = None
    live_control_profile_id: Optional[str] = None
    manual_confirmed: bool = False
    adaptive_mode: AdaptiveMode = "off"
    adaptive_profile_id: Optional[str] = None
    reward_definition_version: Optional[str] = None
    state_definition_version: Optional[str] = None
    rollout_control_version: Optional[str] = None
    prospective_evidence: Optional[ProspectiveEvidenceConfig] = None

    @field_validator("symbols")
    @classmethod
    def symbols_must_be_unique(cls, value: List[str]) -> List[str]:
        normalized = [symbol.strip() for symbol in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols must not contain duplicates")
        return normalized

    @field_validator("features")
    @classmethod
    def features_must_be_unique(cls, value: List[FeatureSpec]) -> List[FeatureSpec]:
        seen: set[tuple[str, int, str]] = set()
        for feature in value:
            key = (feature.name, feature.window, feature.source)
            if key in seen:
                raise ValueError(
                    "features must not contain duplicates with the same name, window, and source"
                )
            seen.add(key)
        return value

    @field_validator("baselines")
    @classmethod
    def baselines_must_be_unique(cls, value: List[BaselineName]) -> List[BaselineName]:
        if len(value) != len(set(value)):
            raise ValueError("baselines must not contain duplicates")
        return value

    @field_validator("scoring_factor_ids")
    @classmethod
    def scoring_factor_ids_must_be_unique(cls, value: List[str]) -> List[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("scoring_factor_ids must not contain duplicates")
        return normalized

    @field_validator("adaptive_profile_id", "reward_definition_version")
    @classmethod
    def adaptive_text_fields_must_not_be_blank(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None

    @field_validator("state_definition_version", "rollout_control_version")
    @classmethod
    def optional_text_fields_must_not_be_blank(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_adaptive_fields(self) -> "ResearchRunCreateRequest":
        if self.adaptive_mode != "off":
            required_fields = {
                "adaptive_profile_id": self.adaptive_profile_id,
                "reward_definition_version": self.reward_definition_version,
                "state_definition_version": self.state_definition_version,
                "rollout_control_version": self.rollout_control_version,
            }
            missing = [field for field, value in required_fields.items() if not value]
            if missing:
                raise ValueError(
                    "adaptive runs require adaptive_profile_id, reward_definition_version, "
                    "state_definition_version, and rollout_control_version"
                )

        if self.prospective_evidence is not None:
            issues = strict_recipe_issues(self.model_dump(mode="json"))
            if issues:
                raise ValueError(
                    "strict prospective evidence requires the canonical recipe: "
                    + ", ".join(issues)
                )
        return self


class BacktestRequest(ResearchRunCreateRequest):
    runtime_mode: str = "runtime_compatibility_mode"
    default_bundle_version: str | None = None


class Metrics(BaseModel):
    total_return: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    turnover: Optional[float] = None
    max_position_weight: Optional[float] = None


class EquityPoint(BaseModel):
    date: date
    equity: float


class SignalPoint(BaseModel):
    date: date
    symbol: str
    score: Optional[float]
    position: float
    signal_kind: Literal["holdout_evaluation", "forward_opinion"] = (
        "holdout_evaluation"
    )
    up_probability: Optional[float] = None
    predicted_direction: Optional[Literal["up", "down"]] = None


class ValidationSummary(BaseModel):
    method: ValidationMethod
    evaluation_status: Literal["evaluated", "not_evaluated"]
    status_reason: Optional[str] = None
    metrics: Dict[str, float]

    @model_validator(mode="after")
    def status_matches_metrics(self) -> "ValidationSummary":
        if self.evaluation_status == "evaluated":
            if not self.metrics:
                raise ValueError("evaluated validation requires non-empty metrics")
            return self
        if self.metrics:
            raise ValueError("not_evaluated validation must not include metrics")
        if not self.status_reason:
            raise ValueError("not_evaluated validation requires status_reason")
        return self


class RegressionDiagnosticPoint(BaseModel):
    date: date
    symbol: str
    actual: float
    predicted: float
    residual: float


class FeatureImportancePoint(BaseModel):
    feature: str
    importance: float


class DirectionClassificationDiagnostics(BaseModel):
    task: Literal["binary_classification"] = "binary_classification"
    evaluation_status: Literal["evaluated", "not_evaluated"]
    status_reason: Optional[str] = None
    sample_count: int = Field(
        default=0,
        description="Holdout rows pooled across all evaluated symbols.",
    )
    positive_return_threshold: float = 0.0
    confirmation_probability_threshold: float = 0.5
    calibration_method: Literal["sigmoid"] = "sigmoid"
    calibration_policy_version: Literal[
        "chronological_tail_20pct_min20_class5_v1"
    ] = "chronological_tail_20pct_min20_class5_v1"
    confirmation_policy_version: Literal[
        "regression_threshold_direction_probability_v1"
    ] = "regression_threshold_direction_probability_v1"
    calibration_sample_count: int = Field(
        default=0,
        description="Sum of calibration rows across all evaluated symbols.",
    )
    positive_prevalence: Optional[float] = None
    confusion_matrix: List[List[int]] = Field(default_factory=list)
    precision: Optional[float] = None
    recall: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    brier: Optional[float] = None


class RegressionDiagnostics(BaseModel):
    task: Literal["regression"] = "regression"
    sample_count: int = 0
    rmse: Optional[float] = None
    mae: Optional[float] = None
    rank_ic: Optional[float] = None
    linear_ic: Optional[float] = None
    actual_vs_predicted: List[RegressionDiagnosticPoint] = Field(default_factory=list)
    residuals: List[RegressionDiagnosticPoint] = Field(default_factory=list)
    feature_importance: List[FeatureImportancePoint] = Field(default_factory=list)
    direction_classification: Optional[DirectionClassificationDiagnostics] = None


class ComparisonCaveat(BaseModel):
    code: str
    label: str
    severity: Literal["blocker", "note"] = "blocker"


OpinionArtifactState = Literal["viable", "no-opinion", "do-not-adopt"]
OpinionReviewCheckName = Literal[
    "strategy_lifecycle",
    "signal_to_position",
    "backtest_report_discipline",
    "robustness",
    "parameter_sensitivity",
    "evidence_traceability",
    "risk_present",
    "invalidation_present",
    "manual_adoption_boundary",
    "insufficient_evidence_gate",
    "source_artifact_audit",
    "text_evidence_summary",
]
OpinionReviewCheckCategory = Literal[
    "method",
    "self_review",
    "source_provider_audit",
    "evidence_summary",
]
OpinionSourceArtifactName = Literal[
    "request_payload",
    "config_sources",
    "fallback_audit",
    "version_pack",
    "model_diagnostics",
    "signals",
    "metrics",
    "baselines",
    "validation",
    "warnings",
    "artifact_completeness",
    "comparison_caveats",
]
OpinionReviewCheckStatus = Literal["pass", "warning", "fail", "not_evaluated"]


def _default_opinion_artifact() -> "OpinionArtifact":
    return OpinionArtifact(
        state="no-opinion",
        state_reason="Opinion artifact has not been built from persisted research artifacts.",
        buy_candidates=[],
        sell_or_avoid=[],
        watch=[],
    )


class OpinionSourceArtifactReference(BaseModel):
    artifact: OpinionSourceArtifactName
    field: str
    symbol: Optional[str] = None
    date: Optional[str] = None


class OpinionRow(BaseModel):
    symbol: str
    model_score: float
    position_signal: float
    signal_date: date
    up_probability: float
    confirmation_state: Literal["confirmed", "conflict"]
    evidence_reason: str
    risk_or_warning: str
    invalidation_note: str
    source_artifact_references: List[OpinionSourceArtifactReference] = Field(
        min_length=1,
    )


class OpinionReviewCheck(BaseModel):
    check: OpinionReviewCheckName
    category: OpinionReviewCheckCategory
    status: OpinionReviewCheckStatus
    evidence_reason: str
    risk_or_warning: str
    source_artifact_references: List[OpinionSourceArtifactReference] = Field(
        min_length=1,
    )
    result: Dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_result_for_evaluated_check(self) -> "OpinionReviewCheck":
        if self.status != "not_evaluated" and not self.result:
            raise ValueError("evaluated review checks require a non-empty result")
        return self


class OpinionArtifact(BaseModel):
    artifact_version: str = "phase2_opinion_artifact_v1"
    state: OpinionArtifactState
    state_reason: str
    manual_adoption_only: Literal[True] = True
    opinion_as_of: Optional[date] = None
    evidence_limitations: List[str] = Field(default_factory=list)
    buy_candidates: List[OpinionRow] = Field(default_factory=list)
    sell_or_avoid: List[OpinionRow] = Field(default_factory=list)
    watch: List[OpinionRow] = Field(default_factory=list)
    review_checks: List[OpinionReviewCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def opinion_rows_match_as_of(self) -> "OpinionArtifact":
        rows = [*self.buy_candidates, *self.sell_or_avoid, *self.watch]
        if rows and (
            self.opinion_as_of is None
            or any(row.signal_date != self.opinion_as_of for row in rows)
        ):
            raise ValueError(
                "opinion rows must share the persisted opinion_as_of date"
            )
        return self


class ReviewArtifactSummaryMixin(BaseModel):
    artifact_completeness: ArtifactCompleteness = "metadata_only"
    present_artifacts: List[ReviewArtifactName] = Field(default_factory=list)
    missing_artifacts: List[ReviewArtifactName] = Field(default_factory=list)
    not_required_artifacts: List[ReviewArtifactName] = Field(default_factory=list)
    comparison_caveats: List[ComparisonCaveat] = Field(default_factory=list)


class ResearchRunResponse(
    VersionPackMixin,
    P3SummaryMixin,
    GovernanceMetadataMixin,
    FoundationMetadataMixin,
    ReviewArtifactSummaryMixin,
):
    run_id: str
    metrics: Metrics
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    signals: List[SignalPoint] = Field(default_factory=list)
    validation: Optional[ValidationSummary] = None
    model_diagnostics: Optional[RegressionDiagnostics] = None
    baselines: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    opinion_artifact: OpinionArtifact = Field(
        default_factory=_default_opinion_artifact
    )
    runtime_mode: RuntimeMode
    default_bundle_version: Optional[DefaultBundleVersion] = None
    effective_strategy: EffectiveStrategyConfig
    config_sources: ConfigSources
    fallback_audit: FallbackAudit


class ResearchRunRecordResponse(
    VersionPackMixin,
    P3SummaryMixin,
    GovernanceMetadataMixin,
    FoundationMetadataMixin,
    ReviewArtifactSummaryMixin,
):
    run_id: str
    request_id: Optional[str] = None
    status: RunStatus
    market: Optional[str] = None
    symbols: List[str] = Field(default_factory=list)
    strategy_type: Optional[str] = None
    runtime_mode: Optional[str] = None
    default_bundle_version: Optional[str] = None
    effective_strategy: Optional[EffectiveStrategyConfig] = None
    allow_proactive_sells: Optional[bool] = None
    config_sources: Optional[ConfigSources] = None
    fallback_audit: Optional[FallbackAudit] = None
    validation_outcome: Optional[Dict[str, object]] = None
    rejection_reason: Optional[str] = None
    request_payload: Optional[Dict[str, object]] = None
    metrics: Optional[Metrics] = None
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    signals: List[SignalPoint] = Field(default_factory=list)
    validation: Optional[ValidationSummary] = None
    model_diagnostics: Optional[RegressionDiagnostics] = None
    baselines: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    opinion_artifact: OpinionArtifact = Field(
        default_factory=_default_opinion_artifact
    )
    created_at: datetime
