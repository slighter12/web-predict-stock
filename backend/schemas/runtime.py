from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel

from .common import (
    ComparisonEligibility,
    ConfigValueSource,
    FallbackOutcome,
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
