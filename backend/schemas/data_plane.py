from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, conint

from .common import (
    ImportantEventType,
    LifecycleEventType,
    MarketCode,
    RecoveryDrillStatus,
    ReplayStatus,
    RequestModel,
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
    raw_payload_id: int
    replay_run_id: Optional[int] = None
    benchmark_profile_id: Optional[str] = None
    notes: Optional[str] = None
    status: RecoveryDrillStatus
    latest_replayable_day: Optional[date] = None
    completed_trading_day_delta: Optional[int] = None
    abort_reason: Optional[str] = None
    drill_started_at: datetime
    drill_completed_at: Optional[datetime] = None
    created_at: datetime


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
