from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request

from ..api_models import BacktestRequest, BacktestResponse
from ..runtime.request_context import get_request_id
from ..schemas.research_runs import (
    ResearchRunCreateRequest,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)
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


@router.post("/api/v1/backtest", tags=["Research Runs"], response_model=BacktestResponse)
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
