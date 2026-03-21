from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from .common import (
    ComparisonEligibility,
    ConfigValueSource,
    CorporateEventState,
    FallbackOutcome,
    MissingFeaturePolicyState,
    MonitorObservationStatus,
    TradabilityContractVersion,
    TradabilityState,
    VersionFieldStatus,
)


class StrategyConfigSources(BaseModel):
    threshold: ConfigValueSource
    top_n: ConfigValueSource


class ConfigSources(BaseModel):
    strategy: StrategyConfigSources


class FallbackAuditEntry(BaseModel):
    attempted: bool
    outcome: FallbackOutcome


class StrategyFallbackAudit(BaseModel):
    threshold: FallbackAuditEntry
    top_n: FallbackAuditEntry


class FallbackAudit(BaseModel):
    strategy: StrategyFallbackAudit


class EffectiveStrategyConfig(BaseModel):
    threshold: float
    top_n: int


class VersionPackMixin(BaseModel):
    threshold_policy_version: Optional[str] = None
    price_basis_version: Optional[str] = None
    benchmark_comparability_gate: Optional[bool] = None
    comparison_eligibility: Optional[ComparisonEligibility] = None
    investability_screening_active: Optional[bool] = None
    capacity_screening_version: Optional[str] = None
    adv_basis_version: Optional[str] = None
    missing_feature_policy_version: Optional[str] = None
    execution_cost_model_version: Optional[str] = None
    split_policy_version: Optional[str] = None
    bootstrap_policy_version: Optional[str] = None
    ic_overlap_policy_version: Optional[str] = None
    version_pack_status: Dict[str, VersionFieldStatus]


class LiquidityBucketCoverage(BaseModel):
    bucket_key: str
    bucket_label: str
    full_universe_count: int
    execution_universe_count: int
    full_universe_ratio: float
    execution_coverage_ratio: float


class P3SummaryMixin(BaseModel):
    tradability_state: Optional[TradabilityState] = None
    tradability_contract_version: Optional[TradabilityContractVersion] = None
    capacity_screening_active: Optional[bool] = None
    missing_feature_policy_state: Optional[MissingFeaturePolicyState] = None
    corporate_event_state: Optional[CorporateEventState] = None
    full_universe_count: Optional[int] = None
    execution_universe_count: Optional[int] = None
    execution_universe_ratio: Optional[float] = None
    liquidity_bucket_schema_version: Optional[str] = None
    liquidity_bucket_coverages: list[LiquidityBucketCoverage] = Field(
        default_factory=list
    )
    stale_mark_days_with_open_positions: Optional[int] = None
    stale_risk_share: Optional[float] = None
    monitor_observation_status: Optional[MonitorObservationStatus] = None
