from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Request
from pydantic import Field, confloat, conint, conlist, field_validator

from backend.platform.http.request_context import get_request_id
from backend.research.contracts.adaptive import (
    AdaptiveProfileRequest,
    AdaptiveProfileResponse,
    AdaptiveTrainingRunRequest,
    AdaptiveTrainingRunResponse,
)
from backend.research.contracts.governance import (
    ResearchMicroKpiResponse,
    ResearchPhaseGateResponse,
)
from backend.research.contracts.runs import (
    BacktestRequest,
    DateRange,
    ExecutionConfig,
    FeatureRegistryResponse,
    FeatureSpec,
    ModelConfig,
    ResearchRunCreateRequest,
    ResearchRunRecordResponse,
    ResearchRunResponse,
    StrategyConfig,
    ValidationConfig,
)
from backend.shared.contracts.common import (
    BaselineName,
    DefaultBundleVersion,
    PriceSource,
    RequestModel,
    ResearchMonitorProfileId,
    ReturnTarget,
    RuntimeMode,
)
from backend.research.services.adaptive import (
    create_adaptive_profile_record,
    create_adaptive_training_run_record,
    list_adaptive_profile_records,
    list_adaptive_training_run_records,
)
from backend.research.services.capability_gates import (
    get_p7_phase_gate_summary,
    get_p8_phase_gate_summary,
    get_p9_phase_gate_summary,
    get_p10_phase_gate_summary,
    get_p11_phase_gate_summary,
)
from backend.research.services.governance import get_p3_phase_gate_summary
from backend.research.services.micro_kpis import get_micro_kpi_summary
from backend.research.services.runs import (
    create_research_run,
    get_research_run,
    list_research_runs,
)
from backend.shared.analytics.features import (
    FEATURE_REGISTRY_VERSION,
    list_feature_definitions,
)

router = APIRouter()


class PublicResearchRunCreateRequest(RequestModel):
    runtime_mode: RuntimeMode = "runtime_compatibility_mode"
    default_bundle_version: DefaultBundleVersion | None = None
    market: Literal["TW"] = "TW"
    symbols: conlist(str, min_length=1)  # type: ignore[valid-type]
    date_range: DateRange
    return_target: ReturnTarget = "open_to_open"
    horizon_days: conint(ge=1) = 1  # type: ignore[valid-type]
    features: list[FeatureSpec]
    model: ModelConfig = Field(default_factory=ModelConfig)
    strategy: StrategyConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    validation: ValidationConfig | None = None
    baselines: list[BaselineName] = Field(default_factory=list)
    portfolio_aum: confloat(gt=0) | None = None  # type: ignore[valid-type]
    monitor_profile_id: ResearchMonitorProfileId | None = None

    @field_validator("symbols")
    @classmethod
    def symbols_must_be_unique(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip() for symbol in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols must not contain duplicates")
        return normalized

    @field_validator("features")
    @classmethod
    def features_must_be_unique(cls, value: list[FeatureSpec]) -> list[FeatureSpec]:
        seen: set[tuple[str, int, PriceSource]] = set()
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
    def baselines_must_be_unique(cls, value: list[BaselineName]) -> list[BaselineName]:
        if len(value) != len(set(value)):
            raise ValueError("baselines must not contain duplicates")
        return value

    @field_validator("date_range")
    @classmethod
    def end_after_start(cls, value: DateRange) -> DateRange:
        if value.end < value.start:
            raise ValueError("end must be on or after start")
        return value

    def to_internal_request(self) -> ResearchRunCreateRequest:
        return ResearchRunCreateRequest(**self.model_dump())


def _create_research_run_response(
    http_request: Request, request: ResearchRunCreateRequest
) -> ResearchRunResponse:
    run_id = str(uuid4())
    http_request.state.run_id = run_id
    return create_research_run(
        request=request,
        request_id=get_request_id(http_request),
        run_id=run_id,
    )


@router.post(
    "/api/v1/research/runs", tags=["Research Runs"], response_model=ResearchRunResponse
)
def create_research_run_endpoint(
    http_request: Request, request: PublicResearchRunCreateRequest
) -> ResearchRunResponse:
    return _create_research_run_response(http_request, request.to_internal_request())


@router.post(
    "/api/v1/backtest", tags=["Research Runs"], response_model=ResearchRunResponse
)
def create_backtest_endpoint(
    http_request: Request, request: BacktestRequest
) -> ResearchRunResponse:
    return _create_research_run_response(http_request, request)


@router.get(
    "/api/v1/research/runs/{run_id}",
    tags=["Research Runs"],
    response_model=ResearchRunRecordResponse,
)
def read_research_run(run_id: str) -> ResearchRunRecordResponse:
    return get_research_run(run_id)


@router.get(
    "/api/v1/research/runs",
    tags=["Research Runs"],
    response_model=list[ResearchRunRecordResponse],
)
def read_research_runs() -> list[ResearchRunRecordResponse]:
    return list_research_runs()


@router.get(
    "/api/v1/research/feature-registry",
    tags=["Research Runs"],
    response_model=FeatureRegistryResponse,
)
def read_feature_registry() -> FeatureRegistryResponse:
    return FeatureRegistryResponse(
        version=FEATURE_REGISTRY_VERSION,
        features=list_feature_definitions(),
    )


@router.get(
    "/api/v1/research/gates/p3",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p3_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p3_phase_gate_summary())


@router.get(
    "/api/v1/research/micro-kpis",
    tags=["Research Runs"],
    response_model=ResearchMicroKpiResponse,
)
def read_micro_kpis(market: str = "TW") -> ResearchMicroKpiResponse:
    return ResearchMicroKpiResponse(**get_micro_kpi_summary(market=market))


@router.get(
    "/api/v1/research/gates/p7",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p7_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p7_phase_gate_summary())


@router.get(
    "/api/v1/research/gates/p8",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p8_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p8_phase_gate_summary())


@router.get(
    "/api/v1/research/gates/p9",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p9_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p9_phase_gate_summary())


@router.get(
    "/api/v1/research/gates/p10",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p10_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p10_phase_gate_summary())


@router.get(
    "/api/v1/research/gates/p11",
    tags=["Research Runs"],
    response_model=ResearchPhaseGateResponse,
)
def read_p11_gate() -> ResearchPhaseGateResponse:
    return ResearchPhaseGateResponse(**get_p11_phase_gate_summary())


@router.post(
    "/api/v1/research/adaptive-profiles",
    tags=["Research Runs"],
    response_model=AdaptiveProfileResponse,
)
def create_adaptive_profile_endpoint(
    request: AdaptiveProfileRequest,
) -> AdaptiveProfileResponse:
    return AdaptiveProfileResponse(**create_adaptive_profile_record(request))


@router.get(
    "/api/v1/research/adaptive-profiles",
    tags=["Research Runs"],
    response_model=list[AdaptiveProfileResponse],
)
def read_adaptive_profiles() -> list[AdaptiveProfileResponse]:
    return [AdaptiveProfileResponse(**item) for item in list_adaptive_profile_records()]


@router.post(
    "/api/v1/research/adaptive-training-runs",
    tags=["Research Runs"],
    response_model=AdaptiveTrainingRunResponse,
)
def create_adaptive_training_run_endpoint(
    request: AdaptiveTrainingRunRequest,
) -> AdaptiveTrainingRunResponse:
    return AdaptiveTrainingRunResponse(**create_adaptive_training_run_record(request))


@router.get(
    "/api/v1/research/adaptive-training-runs",
    tags=["Research Runs"],
    response_model=list[AdaptiveTrainingRunResponse],
)
def read_adaptive_training_runs() -> list[AdaptiveTrainingRunResponse]:
    return [
        AdaptiveTrainingRunResponse(**item)
        for item in list_adaptive_training_run_records()
    ]
