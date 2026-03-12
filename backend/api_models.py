from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, conint, confloat, conlist, field_validator

MarketCode = Literal["TW", "US"]
PriceSource = Literal["open", "high", "low", "close", "volume"]
FeatureName = Literal["ma", "rsi"]
ReturnTarget = Literal["open_to_open", "close_to_close", "open_to_close"]
ModelType = Literal["xgboost"]
StrategyType = Literal["research_v1"]
ValidationMethod = Literal["holdout", "walk_forward", "rolling_window", "expanding_window"]
BaselineName = Literal["buy_and_hold", "naive_momentum", "ma_crossover"]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    type: StrategyType = Field(default="research_v1", description="Strategy identifier.")
    threshold: confloat(ge=0)  # type: ignore[valid-type]
    top_n: conint(ge=1)  # type: ignore[valid-type]
    allow_proactive_sells: bool = True


class ExecutionConfig(RequestModel):
    slippage: confloat(ge=0) = 0.0  # type: ignore[valid-type]
    fees: confloat(ge=0) = 0.0  # type: ignore[valid-type]


class ValidationConfig(RequestModel):
    method: ValidationMethod = "walk_forward"
    splits: conint(ge=1) = 3  # type: ignore[valid-type]
    test_size: confloat(gt=0, lt=1) = 0.2  # type: ignore[valid-type]


class BacktestRequest(RequestModel):
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


class BacktestResponse(BaseModel):
    run_id: str
    metrics: Metrics
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    signals: List[SignalPoint] = Field(default_factory=list)
    validation: Optional[ValidationSummary] = None
    baselines: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
