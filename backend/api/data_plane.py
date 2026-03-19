from __future__ import annotations

from fastapi import APIRouter

from ..schemas.data_plane import (
    DataIngestionRequest,
    DataIngestionResponse,
    ImportantEventResponse,
    ImportantEventUpsert,
    LifecycleRecordResponse,
    LifecycleRecordUpsert,
    RecoveryDrillRequest,
    RecoveryDrillResponse,
    ReplayRequest,
    ReplayResponse,
)
from ..services.data_ingestion_service import ingest_market_data
from ..services.important_event_service import (
    list_important_events,
    save_important_event,
)
from ..services.lifecycle_service import list_lifecycle, save_lifecycle_record
from ..services.recovery_service import create_recovery_drill, list_recovery_drills
from ..services.replay_service import list_replays, replay_raw_payload

router = APIRouter()


@router.post(
    "/api/v1/data/ingestions", tags=["Data Plane"], response_model=DataIngestionResponse
)
def create_data_ingestion(request: DataIngestionRequest) -> DataIngestionResponse:
    summary = ingest_market_data(
        symbol=request.symbol,
        market=request.market,
        years=request.years,
        date_str=request.date_str,
    )
    return DataIngestionResponse(**summary)


@router.post("/api/v1/data/replays", tags=["Data Plane"], response_model=ReplayResponse)
def create_replay(request: ReplayRequest) -> ReplayResponse:
    return ReplayResponse(
        **replay_raw_payload(
            raw_payload_id=request.raw_payload_id,
            benchmark_profile_id=request.benchmark_profile_id,
            notes=request.notes,
        )
    )


@router.get(
    "/api/v1/data/replays", tags=["Data Plane"], response_model=list[ReplayResponse]
)
def read_replays() -> list[ReplayResponse]:
    return [ReplayResponse(**item) for item in list_replays()]


@router.post(
    "/api/v1/data/recovery-drills",
    tags=["Data Plane"],
    response_model=RecoveryDrillResponse,
)
def create_recovery_drill_endpoint(
    request: RecoveryDrillRequest,
) -> RecoveryDrillResponse:
    return RecoveryDrillResponse(
        **create_recovery_drill(
            raw_payload_id=request.raw_payload_id,
            benchmark_profile_id=request.benchmark_profile_id,
            notes=request.notes,
        )
    )


@router.get(
    "/api/v1/data/recovery-drills",
    tags=["Data Plane"],
    response_model=list[RecoveryDrillResponse],
)
def read_recovery_drills() -> list[RecoveryDrillResponse]:
    return [RecoveryDrillResponse(**item) for item in list_recovery_drills()]


@router.post(
    "/api/v1/data/lifecycle-records",
    tags=["Data Plane"],
    response_model=LifecycleRecordResponse,
)
def create_lifecycle_record(request: LifecycleRecordUpsert) -> LifecycleRecordResponse:
    return LifecycleRecordResponse(
        **save_lifecycle_record(request.model_dump(mode="python"))
    )


@router.get(
    "/api/v1/data/lifecycle-records",
    tags=["Data Plane"],
    response_model=list[LifecycleRecordResponse],
)
def read_lifecycle_records() -> list[LifecycleRecordResponse]:
    return [LifecycleRecordResponse(**item) for item in list_lifecycle()]


@router.post(
    "/api/v1/data/important-events",
    tags=["Data Plane"],
    response_model=ImportantEventResponse,
)
def create_important_event(request: ImportantEventUpsert) -> ImportantEventResponse:
    return ImportantEventResponse(
        **save_important_event(request.model_dump(mode="python"))
    )


@router.get(
    "/api/v1/data/important-events",
    tags=["Data Plane"],
    response_model=list[ImportantEventResponse],
)
def read_important_events() -> list[ImportantEventResponse]:
    return [ImportantEventResponse(**item) for item in list_important_events()]
