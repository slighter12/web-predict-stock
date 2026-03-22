from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from backend.shared.contracts.common import (
    AdaptiveMode,
    ExecutionOrderSide,
    ExecutionRoute,
    MarketCode,
    RequestModel,
)


class ExternalSignalIngestionRequest(RequestModel):
    market: MarketCode = "TW"
    source_family: str = "tw_company_event_layer_v1"
    coverage_start: date
    coverage_end: date
    notes: Optional[str] = None

    @field_validator("coverage_end")
    @classmethod
    def end_after_start(cls, value: date, info: Any) -> date:
        start = info.data.get("coverage_start")
        if start and value < start:
            raise ValueError("coverage_end must be on or after coverage_start")
        return value


class ExternalRawArchiveResponse(BaseModel):
    id: int
    source_family: str
    market: MarketCode
    coverage_start: date
    coverage_end: date
    record_count: int
    payload_body: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class ExternalSignalRecordResponse(BaseModel):
    id: int
    archive_id: Optional[int] = None
    source_family: str
    source_record_type: str
    symbol: str
    market: MarketCode
    effective_date: date
    available_at: Optional[datetime] = None
    availability_mode: str
    lineage_version: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ExternalSignalAuditRequest(RequestModel):
    market: MarketCode = "TW"
    source_family: str = "tw_company_event_layer_v1"
    audit_window_start: date
    audit_window_end: date


class ExternalSignalAuditResponse(BaseModel):
    id: int
    source_family: str
    market: MarketCode
    audit_window_start: date
    audit_window_end: date
    sample_size: int
    fallback_sample_size: int
    undocumented_count: int
    draw_rule_version: str
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class FactorCatalogEntryRequest(RequestModel):
    factor_id: str
    display_name: str
    formula_definition: str
    lineage: str
    timing_semantics: str
    missing_value_policy: str
    scoring_eligible: bool = False


class FactorCatalogRequest(RequestModel):
    id: str
    market: MarketCode = "TW"
    source_family: str = "tw_company_event_layer_v1"
    lineage_version: str
    minimum_coverage_ratio: float = 0.8
    is_active: bool = True
    notes: Optional[str] = None
    entries: list[FactorCatalogEntryRequest] = Field(default_factory=list)


class FactorCatalogEntryResponse(BaseModel):
    id: int
    catalog_id: str
    factor_id: str
    display_name: str
    formula_definition: str
    lineage: str
    timing_semantics: str
    missing_value_policy: str
    scoring_eligible: bool
    created_at: datetime


class FactorCatalogResponse(BaseModel):
    id: str
    market: MarketCode
    source_family: str
    lineage_version: str
    minimum_coverage_ratio: float
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    entries: list[FactorCatalogEntryResponse] = Field(default_factory=list)


class FactorMaterializationResponse(BaseModel):
    id: int
    run_id: Optional[str] = None
    catalog_id: Optional[str] = None
    factor_id: str
    symbol: str
    market: MarketCode
    trading_date: date
    value: Optional[float] = None
    source_available_at: Optional[datetime] = None
    factor_available_ts: Optional[datetime] = None
    availability_mode: str
    created_at: datetime


class ClusterSnapshotRequest(RequestModel):
    market: MarketCode = "TW"
    trading_date: date
    snapshot_version: str = "peer_cluster_kmeans_v1"
    factor_catalog_version: Optional[str] = None
    cluster_count: int = 3
    notes: Optional[str] = None


class ClusterMembershipResponse(BaseModel):
    id: int
    snapshot_id: int
    symbol: str
    cluster_label: str
    distance_to_centroid: Optional[float] = None
    created_at: datetime


class ClusterSnapshotResponse(BaseModel):
    id: int
    snapshot_version: str
    run_id: Optional[str] = None
    factor_catalog_version: Optional[str] = None
    market: MarketCode
    trading_date: date
    cluster_count: int
    symbol_count: int
    status: str
    notes: Optional[str] = None
    memberships: list[ClusterMembershipResponse] = Field(default_factory=list)
    created_at: datetime


class PeerFeatureRunRequest(RequestModel):
    snapshot_id: int
    peer_policy_version: str = "cluster_nearest_neighbors_v1"
    symbol_limit: int = 5


class PeerComparisonOverlayResponse(BaseModel):
    id: int
    peer_feature_run_id: int
    symbol: str
    peer_symbol_count: int
    peer_feature_value: Optional[float] = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PeerFeatureRunResponse(BaseModel):
    id: int
    run_id: Optional[str] = None
    snapshot_id: Optional[int] = None
    peer_policy_version: str
    market: MarketCode
    trading_date: date
    status: str
    produced_feature_count: int
    warning_count: int
    warnings: list[str] = Field(default_factory=list)
    overlays: list[PeerComparisonOverlayResponse] = Field(default_factory=list)
    created_at: datetime


class SimulationOrderRequest(RequestModel):
    run_id: Optional[str] = None
    market: MarketCode = "TW"
    symbol: str
    side: ExecutionOrderSide
    quantity: float
    requested_price: Optional[float] = None
    simulation_profile_id: Optional[str] = None


class ExecutionOrderEventResponse(BaseModel):
    id: int
    order_id: int
    event_type: str
    event_ts: datetime
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ExecutionFillEventResponse(BaseModel):
    id: int
    order_id: int
    fill_ts: datetime
    fill_price: float
    quantity: float
    slippage_bps: Optional[float] = None
    created_at: datetime


class ExecutionPositionSnapshotResponse(BaseModel):
    id: int
    order_id: Optional[int] = None
    run_id: Optional[str] = None
    route: ExecutionRoute
    market: MarketCode
    symbol: str
    quantity: float
    avg_price: float
    snapshot_ts: datetime
    created_at: datetime


class SimulationOrderResponse(BaseModel):
    id: int
    run_id: Optional[str] = None
    route: ExecutionRoute
    market: MarketCode
    symbol: str
    side: ExecutionOrderSide
    quantity: float
    requested_price: Optional[float] = None
    status: str
    simulation_profile_id: Optional[str] = None
    live_control_profile_id: Optional[str] = None
    failure_code: Optional[str] = None
    manual_confirmation: bool
    rejection_reason: Optional[str] = None
    submitted_at: datetime
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    events: list[ExecutionOrderEventResponse] = Field(default_factory=list)
    fills: list[ExecutionFillEventResponse] = Field(default_factory=list)
    positions: list[ExecutionPositionSnapshotResponse] = Field(default_factory=list)


class LiveOrderRequest(RequestModel):
    run_id: Optional[str] = None
    market: MarketCode = "TW"
    symbol: str
    side: ExecutionOrderSide
    quantity: float
    requested_price: Optional[float] = None
    live_control_profile_id: Optional[str] = None
    manual_confirmed: bool = False


class LiveRiskCheckResponse(BaseModel):
    id: int
    order_id: int
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime
    created_at: datetime


class LiveOrderResponse(SimulationOrderResponse):
    risk_checks: list[LiveRiskCheckResponse] = Field(default_factory=list)


class KillSwitchRequest(RequestModel):
    scope_type: str = "global"
    market: Optional[MarketCode] = None
    is_enabled: bool
    reason: Optional[str] = None


class KillSwitchResponse(BaseModel):
    id: int
    scope_type: str
    market: Optional[MarketCode] = None
    is_enabled: bool
    reason: Optional[str] = None
    created_at: datetime


class AdaptiveProfileRequest(RequestModel):
    id: str
    market: MarketCode = "TW"
    reward_definition_version: str
    state_definition_version: str
    rollout_control_version: str
    notes: Optional[str] = None
    rollout_detail: dict[str, Any] = Field(default_factory=dict)


class AdaptiveProfileResponse(BaseModel):
    id: str
    market: MarketCode
    reward_definition_version: str
    state_definition_version: str
    notes: Optional[str] = None
    rollout_control_version: Optional[str] = None
    rollout_mode: Optional[AdaptiveMode] = None
    rollout_detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AdaptiveTrainingRunRequest(RequestModel):
    adaptive_profile_id: str
    market: MarketCode = "TW"
    adaptive_mode: AdaptiveMode = "shadow"
    reward_definition_version: str
    state_definition_version: str
    rollout_control_version: str
    run_id: Optional[str] = None


class AdaptiveTrainingRunResponse(BaseModel):
    id: int
    profile_id: Optional[str] = None
    run_id: Optional[str] = None
    market: MarketCode
    adaptive_mode: AdaptiveMode
    reward_definition_version: str
    state_definition_version: str
    rollout_control_version: str
    status: str
    dataset_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_registry: dict[str, Any] = Field(default_factory=dict)
    validation_error: Optional[str] = None
    created_at: datetime
