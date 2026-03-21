from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import KpiStatus
from .data_plane import OpsKpiMetricResponse


class ResearchGateArtifactResponse(BaseModel):
    status: KpiStatus
    details: dict[str, Any] = Field(default_factory=dict)


class ResearchPhaseGateResponse(BaseModel):
    gate_id: str
    verification_gate_id: str
    overall_status: KpiStatus
    metrics: dict[str, OpsKpiMetricResponse]
    artifacts: dict[str, ResearchGateArtifactResponse]
    missing_reasons: list[str] = Field(default_factory=list)


class ResearchMicroKpiResponse(BaseModel):
    gate_id: str
    overall_status: KpiStatus
    metrics: dict[str, OpsKpiMetricResponse]
    selection_policy: dict[str, Any] = Field(default_factory=dict)
    binding_status: str = "bootstrap_only"
    binding_reason: Optional[str] = None
