from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, conint, confloat, conlist, validator

PriceSource = Literal["open", "high", "low", "close", "volume"]
FeatureName = Literal["ma", "rsi"]
ReturnTarget = Literal["open_to_open", "close_to_close", "open_to_close"]


class DateRange(BaseModel):
    start: date = Field(..., description="Inclusive start date.")
    end: date = Field(..., description="Inclusive end date.")

    @validator("end")
    def end_after_start(cls, value: date, values: Dict[str, date]) -> date:
        start = values.get("start")
        if start and value < start:
            raise ValueError("end must be on or after start")
        return value


class FeatureSpec(BaseModel):
    name: FeatureName
    window: conint(ge=1)  # type: ignore[valid-type]
    source: PriceSource = "close"
    shift: conint(ge=0) = 1  # type: ignore[valid-type]


class ModelConfig(BaseModel):
    type: str = Field(..., description="Model identifier, e.g. xgboost.")
    params: Dict[str, object] = Field(default_factory=dict)


class SelectionConfig(BaseModel):
    threshold_metric: str
    threshold: confloat(ge=0)  # type: ignore[valid-type]
    top_n: conint(ge=1)  # type: ignore[valid-type]
    weighting: str = "equal"


class TradingRules(BaseModel):
    rebalance: str = "daily_open"
    allow_same_day_reinvest: bool = True
    allow_intraday: bool = False
    allow_leverage: bool = False


class ExitRules(BaseModel):
    allow_proactive_sells: bool = True
    default_liquidation: str = "next_open"


class ExecutionConfig(BaseModel):
    matching_model: str = "ohlc_default"
    slippage: confloat(ge=0) = 0.0  # type: ignore[valid-type]
    fees: confloat(ge=0) = 0.0  # type: ignore[valid-type]


class ValidationConfig(BaseModel):
    method: str = "walk_forward"
    splits: conint(ge=1) = 3  # type: ignore[valid-type]
    test_size: confloat(gt=0, lt=1) = 0.2  # type: ignore[valid-type]


class BacktestRequest(BaseModel):
    market: str = Field(..., description="Market code, e.g. TW or US.")
    symbols: conlist(str, min_length=1)  # type: ignore[valid-type]
    date_range: DateRange
    return_target: ReturnTarget = "open_to_open"
    horizon_days: conint(ge=1) = 1  # type: ignore[valid-type]
    features: List[FeatureSpec]
    model: ModelConfig = Field(default_factory=lambda: ModelConfig(type="xgboost"))
    selection: SelectionConfig
    trading_rules: TradingRules = Field(default_factory=TradingRules)
    exit_rules: ExitRules = Field(default_factory=ExitRules)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    validation: Optional[ValidationConfig] = None
    baselines: List[str] = Field(default_factory=list)


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
    method: str
    metrics: Dict[str, float]


class BacktestResponse(BaseModel):
    run_id: str
    metrics: Metrics
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    signals: List[SignalPoint] = Field(default_factory=list)
    validation: Optional[ValidationSummary] = None
    baselines: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
