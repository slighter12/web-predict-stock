from __future__ import annotations

from datetime import date

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from ..schemas.data_plane import (
    BenchmarkProfileRequest,
    BenchmarkProfileResponse,
    CrawlerRunResponse,
    DataIngestionRequest,
    DataIngestionResponse,
    ImportantEventResponse,
    ImportantEventUpsert,
    IngestionDispatchRequest,
    IngestionDispatchResponse,
    IngestionWatchlistRequest,
    IngestionWatchlistResponse,
    LifecycleRecordResponse,
    LifecycleRecordUpsert,
    OpsKpiResponse,
    RecoveryDrillRequest,
    RecoveryDrillResponse,
    RecoveryDrillScheduleRequest,
    RecoveryDrillScheduleResponse,
    ReplayRequest,
    ReplayResponse,
    TickArchiveDispatchRequest,
    TickArchiveImportResponse,
    TickArchiveObjectResponse,
    TickArchiveRunResponse,
    TickOpsKpiResponse,
    TickPhaseGateResponse,
    TickReplayRequest,
    TickReplayResponse,
    TwCompanyCrawlRequest,
    TwCompanyCrawlerRunResponse,
    TwCompanyProfileResponse,
)
from ..services.benchmark_profile_service import (
    create_benchmark_profile,
    list_registered_benchmark_profiles,
)
from ..services.data_ingestion_service import ingest_market_data
from ..services.important_event_service import (
    list_important_events,
    save_important_event,
)
from ..services.ingestion_watchlist_service import (
    create_ingestion_watchlist_entry,
    list_ingestion_watchlist,
)
from ..services.lifecycle_service import list_lifecycle, save_lifecycle_record
from ..services.official_event_crawler_service import (
    crawl_important_events,
    crawl_lifecycle_records,
)
from ..services.ops_kpi_service import get_ops_kpi_summary
from ..services.recovery_service import (
    create_recovery_drill,
    create_recovery_drill_schedule,
    list_recovery_drills,
    list_recovery_schedules,
)
from ..services.replay_service import list_replays, replay_raw_payload
from ..services.scheduled_ingestion_service import dispatch_due_scheduled_ingestions
from ..services.tick_archive_service import (
    create_tick_archive_dispatch,
    create_tick_archive_import,
    list_tick_archive_dispatches,
    list_tick_archives,
)
from ..services.tick_gate_service import get_tick_phase_gate_summary
from ..services.tick_ops_kpi_service import get_tick_ops_kpi_summary
from ..services.tick_replay_service import create_tick_replay, list_tick_replays
from ..services.tw_company_crawler_service import crawl_tw_company_profiles
from ..services.tw_company_profile_service import (
    count_active_tw_company_profiles,
    list_active_tw_company_profiles,
)

router = APIRouter()


@router.post(
    "/api/v1/data/ingestions", tags=["Data Plane"], response_model=DataIngestionResponse
)
def create_data_ingestion(request: DataIngestionRequest) -> DataIngestionResponse:
    summary = ingest_market_data(request)
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
    "/api/v1/data/tick-archive-dispatches",
    tags=["Data Plane"],
    response_model=TickArchiveRunResponse,
)
def create_tick_archive_dispatch_endpoint(
    request: TickArchiveDispatchRequest,
) -> TickArchiveRunResponse:
    return TickArchiveRunResponse(**create_tick_archive_dispatch(request))


@router.get(
    "/api/v1/data/tick-archive-dispatches",
    tags=["Data Plane"],
    response_model=list[TickArchiveRunResponse],
)
def read_tick_archive_dispatches() -> list[TickArchiveRunResponse]:
    return [TickArchiveRunResponse(**item) for item in list_tick_archive_dispatches()]


@router.post(
    "/api/v1/data/tick-archive-imports",
    tags=["Data Plane"],
    response_model=TickArchiveImportResponse,
)
async def create_tick_archive_import_endpoint(
    market: str = Form(...),
    trading_date: date = Form(...),
    notes: str | None = Form(default=None),
    archive_file: UploadFile = File(...),
) -> TickArchiveImportResponse:
    file_bytes = await archive_file.read()
    result = create_tick_archive_import(
        market=market,
        trading_date=trading_date,
        notes=notes,
        file_bytes=file_bytes,
    )
    return TickArchiveImportResponse(**result)


@router.get(
    "/api/v1/data/tick-archives",
    tags=["Data Plane"],
    response_model=list[TickArchiveObjectResponse],
)
def read_tick_archives() -> list[TickArchiveObjectResponse]:
    return [TickArchiveObjectResponse(**item) for item in list_tick_archives()]


@router.post(
    "/api/v1/data/tw-company-crawls",
    tags=["Data Plane"],
    response_model=TwCompanyCrawlerRunResponse,
)
def create_tw_company_crawl(
    request: TwCompanyCrawlRequest | None = None,
) -> TwCompanyCrawlerRunResponse:
    request = request or TwCompanyCrawlRequest()
    return TwCompanyCrawlerRunResponse(
        **crawl_tw_company_profiles(include_tpex=request.include_tpex)
    )


@router.get(
    "/api/v1/data/tw-company-profiles",
    tags=["Data Plane"],
    response_model=list[TwCompanyProfileResponse],
)
def read_tw_company_profiles(
    response: Response,
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[TwCompanyProfileResponse]:
    response.headers["X-Total-Count"] = str(count_active_tw_company_profiles())
    return [
        TwCompanyProfileResponse(**item)
        for item in list_active_tw_company_profiles(limit=limit, offset=offset)
    ]


@router.post(
    "/api/v1/data/tick-replays",
    tags=["Data Plane"],
    response_model=TickReplayResponse,
)
def create_tick_replay_endpoint(request: TickReplayRequest) -> TickReplayResponse:
    return TickReplayResponse(
        **create_tick_replay(
            archive_object_id=request.archive_object_id,
            benchmark_profile_id=request.benchmark_profile_id,
            notes=request.notes,
        )
    )


@router.get(
    "/api/v1/data/tick-replays",
    tags=["Data Plane"],
    response_model=list[TickReplayResponse],
)
def read_tick_replays() -> list[TickReplayResponse]:
    return [TickReplayResponse(**item) for item in list_tick_replays()]


@router.get(
    "/api/v1/data/tick-ops/kpis",
    tags=["Data Plane"],
    response_model=TickOpsKpiResponse,
)
def read_tick_ops_kpis() -> TickOpsKpiResponse:
    return TickOpsKpiResponse(**get_tick_ops_kpi_summary())


@router.get(
    "/api/v1/data/tick-gates/p2",
    tags=["Data Plane"],
    response_model=TickPhaseGateResponse,
)
def read_tick_phase_gate() -> TickPhaseGateResponse:
    return TickPhaseGateResponse(**get_tick_phase_gate_summary())


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
    "/api/v1/data/recovery-drill-schedules",
    tags=["Data Plane"],
    response_model=RecoveryDrillScheduleResponse,
)
def create_recovery_drill_schedule_endpoint(
    request: RecoveryDrillScheduleRequest,
) -> RecoveryDrillScheduleResponse:
    return RecoveryDrillScheduleResponse(**create_recovery_drill_schedule(request))


@router.get(
    "/api/v1/data/recovery-drill-schedules",
    tags=["Data Plane"],
    response_model=list[RecoveryDrillScheduleResponse],
)
def read_recovery_drill_schedules() -> list[RecoveryDrillScheduleResponse]:
    return [RecoveryDrillScheduleResponse(**item) for item in list_recovery_schedules()]


@router.post(
    "/api/v1/data/benchmark-profiles",
    tags=["Data Plane"],
    response_model=BenchmarkProfileResponse,
)
def create_benchmark_profile_endpoint(
    request: BenchmarkProfileRequest,
) -> BenchmarkProfileResponse:
    return BenchmarkProfileResponse(**create_benchmark_profile(request))


@router.get(
    "/api/v1/data/benchmark-profiles",
    tags=["Data Plane"],
    response_model=list[BenchmarkProfileResponse],
)
def read_benchmark_profiles() -> list[BenchmarkProfileResponse]:
    return [
        BenchmarkProfileResponse(**item)
        for item in list_registered_benchmark_profiles()
    ]


@router.post(
    "/api/v1/data/ingestion-watchlist",
    tags=["Data Plane"],
    response_model=IngestionWatchlistResponse,
)
def create_ingestion_watchlist_endpoint(
    request: IngestionWatchlistRequest,
) -> IngestionWatchlistResponse:
    return IngestionWatchlistResponse(**create_ingestion_watchlist_entry(request))


@router.get(
    "/api/v1/data/ingestion-watchlist",
    tags=["Data Plane"],
    response_model=list[IngestionWatchlistResponse],
)
def read_ingestion_watchlist() -> list[IngestionWatchlistResponse]:
    return [IngestionWatchlistResponse(**item) for item in list_ingestion_watchlist()]


@router.post(
    "/api/v1/data/ingestion-dispatches",
    tags=["Data Plane"],
    response_model=IngestionDispatchResponse,
)
def create_ingestion_dispatch(
    request: IngestionDispatchRequest,
) -> IngestionDispatchResponse:
    return IngestionDispatchResponse(
        **dispatch_due_scheduled_ingestions(
            scheduled_for_date=request.scheduled_for_date,
        )
    )


@router.get(
    "/api/v1/data/ops/kpis",
    tags=["Data Plane"],
    response_model=OpsKpiResponse,
)
def read_ops_kpis() -> OpsKpiResponse:
    return OpsKpiResponse(**get_ops_kpi_summary())


@router.post(
    "/api/v1/data/lifecycle-crawls",
    tags=["Data Plane"],
    response_model=CrawlerRunResponse,
)
def create_lifecycle_crawl() -> CrawlerRunResponse:
    return CrawlerRunResponse(**crawl_lifecycle_records())


@router.post(
    "/api/v1/data/important-event-crawls",
    tags=["Data Plane"],
    response_model=CrawlerRunResponse,
)
def create_important_event_crawl() -> CrawlerRunResponse:
    return CrawlerRunResponse(**crawl_important_events())


@router.post(
    "/api/v1/data/lifecycle-records",
    tags=["Data Plane"],
    response_model=LifecycleRecordResponse,
)
def create_lifecycle_record(request: LifecycleRecordUpsert) -> LifecycleRecordResponse:
    return LifecycleRecordResponse(**save_lifecycle_record(request))


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
    return ImportantEventResponse(**save_important_event(request))


@router.get(
    "/api/v1/data/important-events",
    tags=["Data Plane"],
    response_model=list[ImportantEventResponse],
)
def read_important_events() -> list[ImportantEventResponse]:
    return [ImportantEventResponse(**item) for item in list_important_events()]
