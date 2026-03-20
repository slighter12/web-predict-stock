from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, conint

from .common import (
    ImportantEventType,
    KpiStatus,
    LifecycleEventType,
    MarketCode,
    RecoveryDrillCadence,
    RecoveryDrillStatus,
    RecoveryDrillTriggerMode,
    ReplayStatus,
    RequestModel,
    ScheduledIngestionStatus,
    TimestampSourceClass,
)


class DataIngestionRequest(RequestModel):
    symbol: str
    market: MarketCode = "TW"
    years: conint(ge=1) = 5  # type: ignore[valid-type]
    date_str: Optional[str] = None


class IngestionStageSummary(BaseModel):
    raw_payload_id: Optional[int] = None
    archive_object_reference: Optional[str] = None
    parser_version: Optional[str] = None
    input_rows: int
    validated_rows: int
    dropped_rows: int
    duplicates_removed: int
    null_rows_removed: int
    invalid_rows_removed: int
    gap_warnings: int
    upserted_rows: int
    official_overrides: int


class DataIngestionResponse(BaseModel):
    symbol: str
    market: str
    backfill: IngestionStageSummary
    daily_update: IngestionStageSummary


class ReplayRequest(RequestModel):
    raw_payload_id: int = Field(..., ge=1)
    benchmark_profile_id: Optional[str] = None
    notes: Optional[str] = None


class ReplayResponse(BaseModel):
    id: int
    raw_payload_id: int
    source_name: str
    symbol: str
    market: str
    archive_object_reference: Optional[str] = None
    parser_version: str
    benchmark_profile_id: Optional[str] = None
    notes: Optional[str] = None
    restore_status: ReplayStatus
    abort_reason: Optional[str] = None
    restored_row_count: int
    replay_started_at: datetime
    replay_completed_at: Optional[datetime] = None
    created_at: datetime


class RecoveryDrillRequest(RequestModel):
    raw_payload_id: Optional[int] = Field(default=None, ge=1)
    benchmark_profile_id: Optional[str] = None
    notes: Optional[str] = None


class RecoveryDrillResponse(BaseModel):
    id: int
    raw_payload_id: Optional[int] = None
    replay_run_id: Optional[int] = None
    benchmark_profile_id: Optional[str] = None
    notes: Optional[str] = None
    status: RecoveryDrillStatus
    trigger_mode: RecoveryDrillTriggerMode = "manual"
    schedule_id: Optional[int] = None
    scheduled_for_date: Optional[date] = None
    latest_replayable_day: Optional[date] = None
    completed_trading_day_delta: Optional[int] = None
    abort_reason: Optional[str] = None
    drill_started_at: datetime
    drill_completed_at: Optional[datetime] = None
    created_at: datetime


class RecoveryDrillScheduleRequest(RequestModel):
    market: MarketCode = "TW"
    symbol: Optional[str] = None
    cadence: RecoveryDrillCadence = "monthly"
    day_of_month: conint(ge=1, le=31) = 1  # type: ignore[valid-type]
    timezone: str = "Asia/Taipei"
    benchmark_profile_id: str
    notes: Optional[str] = None


class RecoveryDrillScheduleResponse(BaseModel):
    id: int
    market: MarketCode = "TW"
    symbol: Optional[str] = None
    cadence: RecoveryDrillCadence
    day_of_month: int
    timezone: str
    benchmark_profile_id: str
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime


class BenchmarkProfileRequest(RequestModel):
    id: str
    cpu_class: str
    memory_size: str
    storage_type: str
    compression_settings: str
    archive_layout_version: str
    network_class: str


class BenchmarkProfileResponse(BaseModel):
    id: str
    cpu_class: str
    memory_size: str
    storage_type: str
    compression_settings: str
    archive_layout_version: str
    network_class: str
    created_at: datetime


class IngestionWatchlistRequest(RequestModel):
    symbol: str
    market: MarketCode = "TW"
    years: conint(ge=1) = 5  # type: ignore[valid-type]


class IngestionWatchlistResponse(BaseModel):
    id: int
    symbol: str
    market: MarketCode = "TW"
    years: int
    is_active: bool
    created_at: datetime


class ScheduledIngestionAttemptResponse(BaseModel):
    id: int
    attempt_number: int
    status: ScheduledIngestionStatus
    raw_payload_id: Optional[int] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class ScheduledIngestionRunResponse(BaseModel):
    id: int
    watchlist_id: int
    symbol: str
    market: MarketCode = "TW"
    scheduled_for_date: date
    status: ScheduledIngestionStatus
    attempt_count: int
    last_error_message: Optional[str] = None
    first_attempt_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    attempts: list[ScheduledIngestionAttemptResponse] = Field(default_factory=list)


class IngestionDispatchRequest(RequestModel):
    scheduled_for_date: Optional[date] = None


class IngestionDispatchResponse(BaseModel):
    schedule_count: int
    dispatched_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    records: list[ScheduledIngestionRunResponse] = Field(default_factory=list)


class OpsKpiMetricResponse(BaseModel):
    value: Optional[float] = None
    status: KpiStatus
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    unit: Optional[str] = None
    window: str
    details: dict[str, Any] = Field(default_factory=dict)


class OpsKpiResponse(BaseModel):
    gate_id: str
    overall_status: KpiStatus
    metrics: dict[str, OpsKpiMetricResponse]


class CrawlerRunResponse(BaseModel):
    source_name: str
    raw_payload_id: Optional[int] = None
    processed_count: int
    upserted_count: int
    errors: list[str] = Field(default_factory=list)


class LifecycleRecordUpsert(RequestModel):
    symbol: str
    market: MarketCode = "TW"
    event_type: LifecycleEventType
    effective_date: date
    reference_symbol: Optional[str] = None
    source_name: str
    raw_payload_id: Optional[int] = Field(default=None, ge=1)
    archive_object_reference: Optional[str] = None
    notes: Optional[str] = None


class ImportantEventUpsert(RequestModel):
    symbol: str
    market: MarketCode = "TW"
    event_type: ImportantEventType
    effective_date: Optional[date] = None
    event_publication_ts: datetime
    timestamp_source_class: TimestampSourceClass
    source_name: str
    raw_payload_id: Optional[int] = Field(default=None, ge=1)
    archive_object_reference: Optional[str] = None
    notes: Optional[str] = None


class LifecycleRecordResponse(BaseModel):
    id: int
    symbol: str
    market: MarketCode = "TW"
    event_type: LifecycleEventType
    effective_date: date
    reference_symbol: Optional[str] = None
    source_name: str
    raw_payload_id: Optional[int] = None
    archive_object_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class ImportantEventResponse(BaseModel):
    id: int
    symbol: str
    market: MarketCode = "TW"
    event_type: ImportantEventType
    effective_date: Optional[date] = None
    event_publication_ts: datetime
    timestamp_source_class: TimestampSourceClass
    source_name: str
    raw_payload_id: Optional[int] = None
    archive_object_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
