from __future__ import annotations

from fastapi import APIRouter

from ..schemas.foundations import (
    KillSwitchRequest,
    KillSwitchResponse,
    LiveOrderRequest,
    LiveOrderResponse,
    SimulationOrderRequest,
    SimulationOrderResponse,
)
from ..services.foundation_service import (
    create_kill_switch,
    create_live_order,
    create_simulation_order,
    list_execution_readbacks,
    list_kill_switch_records,
    list_simulation_readbacks,
)

router = APIRouter()


@router.post(
    "/api/v1/execution/simulation-orders",
    tags=["Execution"],
    response_model=SimulationOrderResponse,
)
def create_simulation_order_endpoint(
    request: SimulationOrderRequest,
) -> SimulationOrderResponse:
    return SimulationOrderResponse(**create_simulation_order(request))


@router.get(
    "/api/v1/execution/simulation-readbacks",
    tags=["Execution"],
    response_model=list[SimulationOrderResponse],
)
def read_simulation_readbacks() -> list[SimulationOrderResponse]:
    return [SimulationOrderResponse(**item) for item in list_simulation_readbacks()]


@router.post(
    "/api/v1/execution/live-orders",
    tags=["Execution"],
    response_model=LiveOrderResponse,
)
def create_live_order_endpoint(request: LiveOrderRequest) -> LiveOrderResponse:
    return LiveOrderResponse(**create_live_order(request))


@router.get(
    "/api/v1/execution/live-orders",
    tags=["Execution"],
    response_model=list[LiveOrderResponse],
)
def read_live_orders() -> list[LiveOrderResponse]:
    return [
        LiveOrderResponse(**item) for item in list_execution_readbacks("live_stub_v1")
    ]


@router.post(
    "/api/v1/execution/live-controls/kill-switch",
    tags=["Execution"],
    response_model=KillSwitchResponse,
)
def create_kill_switch_endpoint(request: KillSwitchRequest) -> KillSwitchResponse:
    return KillSwitchResponse(**create_kill_switch(request))


@router.get(
    "/api/v1/execution/live-controls/kill-switch",
    tags=["Execution"],
    response_model=list[KillSwitchResponse],
)
def read_kill_switch_events() -> list[KillSwitchResponse]:
    return [KillSwitchResponse(**item) for item in list_kill_switch_records()]
