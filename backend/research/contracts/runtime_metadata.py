from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from backend.shared.contracts.common import (
    AdaptiveMode,
    ComparisonEligibility,
    ConfigValueSource,
    CorporateEventState,
    ExecutionRoute,
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
    factor_catalog_version: Optional[str] = None
    external_lineage_version: Optional[str] = None
    cluster_snapshot_version: Optional[str] = None
    peer_comparison_policy_version: Optional[str] = None
    simulation_adapter_version: Optional[str] = None
    live_control_version: Optional[str] = None
    adaptive_contract_version: Optional[str] = None
    version_pack_status: Dict[str, VersionFieldStatus]


class GovernanceMetadataMixin(BaseModel):
    comparison_review_matrix_version: Optional[str] = None
    scheduled_review_cadence: Optional[str] = None
    model_family: Optional[str] = None
    training_output_contract_version: Optional[str] = None
    adoption_comparison_policy_version: Optional[str] = None


class FoundationMetadataMixin(BaseModel):
    scoring_factor_ids: list[str] = Field(default_factory=list)
    external_signal_policy_version: Optional[str] = None
    peer_policy_version: Optional[str] = None
    execution_route: Optional[ExecutionRoute] = None
    simulation_profile_id: Optional[str] = None
    live_control_profile_id: Optional[str] = None
    adaptive_mode: Optional[AdaptiveMode] = None
    adaptive_profile_id: Optional[str] = None
    reward_definition_version: Optional[str] = None
    state_definition_version: Optional[str] = None
    rollout_control_version: Optional[str] = None

    @field_validator("scoring_factor_ids", mode="before")
    @classmethod
    def scoring_factor_ids_defaults_to_empty_list(cls, value: object) -> object:
        return [] if value is None else value


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
