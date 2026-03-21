from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    confloat,
    conint,
    conlist,
    field_validator,
)

from .common import (
    BaselineName,
    DefaultBundleVersion,
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
from .runtime import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
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
    shift: conint(ge=0) = 1  # type: ignore[valid-type]


class ModelConfig(RequestModel):
    type: ModelType = Field(default="xgboost", description="Model identifier.")
    params: Dict[str, object] = Field(default_factory=dict)


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
    strategy: StrategyConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    validation: Optional[ValidationConfig] = None
    baselines: List[BaselineName] = Field(default_factory=list)
    portfolio_aum: Optional[confloat(gt=0)] = None  # type: ignore[valid-type]
    monitor_profile_id: Optional[ResearchMonitorProfileId] = None

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


class Metrics(BaseModel):
    total_return: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    turnover: Optional[float] = None


class EquityPoint(BaseModel):
    date: date
    equity: float


class SignalPoint(BaseModel):
    date: date
    symbol: str
    score: float
    position: float


class ValidationSummary(BaseModel):
    method: ValidationMethod
    metrics: Dict[str, float]


class ResearchRunResponse(VersionPackMixin, P3SummaryMixin):
    run_id: str
    metrics: Metrics
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    signals: List[SignalPoint] = Field(default_factory=list)
    validation: Optional[ValidationSummary] = None
    baselines: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    runtime_mode: RuntimeMode
    default_bundle_version: Optional[DefaultBundleVersion] = None
    effective_strategy: EffectiveStrategyConfig
    config_sources: ConfigSources
    fallback_audit: FallbackAudit


class ResearchRunRecordResponse(VersionPackMixin, P3SummaryMixin):
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
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime
