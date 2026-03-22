from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request

from ..api_models import BacktestRequest
from ..runtime.request_context import get_request_id
from ..schemas.foundations import (
    AdaptiveProfileRequest,
    AdaptiveProfileResponse,
    AdaptiveTrainingRunRequest,
    AdaptiveTrainingRunResponse,
)
from ..schemas.research_governance import (
    ResearchMicroKpiResponse,
    ResearchPhaseGateResponse,
)
from ..schemas.research_runs import (
    ResearchRunCreateRequest,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)
from ..services.foundation_gate_service import (
    get_p7_phase_gate_summary,
    get_p8_phase_gate_summary,
    get_p9_phase_gate_summary,
    get_p10_phase_gate_summary,
    get_p11_phase_gate_summary,
)
from ..services.foundation_service import (
    create_adaptive_profile_record,
    create_adaptive_training_run_record,
    list_adaptive_profile_records,
    list_adaptive_training_run_records,
)
from ..services.micro_kpi_service import get_micro_kpi_summary
from ..services.research_gate_service import get_p3_phase_gate_summary
from ..services.research_run_service import (
    create_research_run,
    get_research_run,
    list_research_runs,
)

router = APIRouter()


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
    http_request: Request, request: ResearchRunCreateRequest
) -> ResearchRunResponse:
    return _create_research_run_response(http_request, request)


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
