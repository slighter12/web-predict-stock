from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas.research_runs import (
    DateRange,
    EquityPoint,
    ExecutionConfig,
    FeatureSpec,
    Metrics,
    ModelConfig,
    ResearchRunCreateRequest,
    SignalPoint,
    StrategyConfig,
    ValidationConfig,
    ValidationSummary,
)


class BacktestRequest(ResearchRunCreateRequest):
    runtime_mode: str = "runtime_compatibility_mode"
    default_bundle_version: str | None = None


class BacktestResponse(BaseModel):
    run_id: str
    metrics: Metrics
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    signals: list[SignalPoint] = Field(default_factory=list)
    validation: ValidationSummary | None = None
    baselines: dict[str, dict[str, float]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "BacktestRequest",
    "BacktestResponse",
    "DateRange",
    "ExecutionConfig",
    "FeatureSpec",
    "Metrics",
    "ModelConfig",
    "StrategyConfig",
    "ValidationConfig",
    "ValidationSummary",
]
