import type {
  ImportantEventType,
  KpiStatus,
  LifecycleEventType,
  MarketCode,
  RecoveryDrillCadence,
  RecoveryDrillTriggerMode,
  TimestampSourceClass,
} from "./common";

export interface IngestionStageSummary {
  raw_payload_id: number | null;
  archive_object_reference: string | null;
  parser_version: string | null;
  input_rows: number;
  validated_rows: number;
  dropped_rows: number;
  duplicates_removed: number;
  null_rows_removed: number;
  invalid_rows_removed: number;
  gap_warnings: number;
  upserted_rows: number;
  official_overrides: number;
}

export interface DataIngestionRequest {
  symbol: string;
  market: MarketCode;
  years: number;
  date_str?: string;
}

export interface DataIngestionResponse {
  symbol: string;
  market: string;
  backfill: IngestionStageSummary;
  daily_update: IngestionStageSummary;
}

export interface TwDailyReadinessRequest {
  market: "TW";
  symbols: string[];
  date_range?: {
    start: string;
    end: string;
  };
}

export interface TwDailyReadinessSymbolStatus {
  symbol: string;
  status: "ready" | "warning" | "missing";
  latest_daily_date: string | null;
  latest_raw_fetch_ts: string | null;
  requested_trading_days: number | null;
  covered_trading_days: number | null;
  missing_trading_days: number | null;
  stale_trading_days: number;
  warnings: string[];
}

export interface TwDailyReadinessResponse {
  market: "TW";
  overall_status: "ready" | "warning" | "missing";
  evaluated_at: string;
  date_range: {
    start: string;
    end: string;
  } | null;
  summary: {
    ready: number;
    warning: number;
    missing: number;
    stale: number;
  };
  symbols: TwDailyReadinessSymbolStatus[];
}

export interface ReplayRequest {
  raw_payload_id: number;
  benchmark_profile_id?: string;
  notes?: string;
}

export interface ReplayRecord {
  id: number;
  raw_payload_id: number;
  source_name: string;
  symbol: string;
  market: string;
  archive_object_reference: string | null;
  parser_version: string;
  benchmark_profile_id: string | null;
  notes: string | null;
  restore_status: "succeeded" | "failed";
  abort_reason: string | null;
  restored_row_count: number;
  replay_started_at: string;
  replay_completed_at: string | null;
  created_at: string;
}

export interface RecoveryDrillRequest {
  raw_payload_id?: number;
  benchmark_profile_id?: string;
  notes?: string;
}

export interface RecoveryDrillRecord {
  id: number;
  raw_payload_id: number | null;
  replay_run_id: number | null;
  benchmark_profile_id: string | null;
  notes: string | null;
  status: "succeeded" | "failed";
  trigger_mode: RecoveryDrillTriggerMode;
  schedule_id: number | null;
  scheduled_for_date: string | null;
  latest_replayable_day: string | null;
  completed_trading_day_delta: number | null;
  abort_reason: string | null;
  drill_started_at: string;
  drill_completed_at: string | null;
  created_at: string;
}

export interface RecoveryDrillScheduleRequest {
  market: MarketCode;
  symbol?: string;
  cadence?: RecoveryDrillCadence;
  day_of_month: number;
  timezone?: string;
  benchmark_profile_id: string;
  notes?: string;
}

export interface RecoveryDrillScheduleRecord {
  id: number;
  market: MarketCode;
  symbol: string | null;
  cadence: RecoveryDrillCadence;
  day_of_month: number;
  timezone: string;
  benchmark_profile_id: string;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LifecycleRecordPayload {
  symbol: string;
  market: MarketCode;
  event_type: LifecycleEventType;
  effective_date: string;
  reference_symbol?: string;
  source_name: string;
  raw_payload_id?: number;
  archive_object_reference?: string;
  notes?: string;
}

export interface LifecycleRecord extends LifecycleRecordPayload {
  id: number;
  created_at: string;
}

export interface ImportantEventPayload {
  symbol: string;
  market: MarketCode;
  event_type: ImportantEventType;
  effective_date?: string;
  event_publication_ts: string;
  timestamp_source_class: TimestampSourceClass;
  source_name: string;
  raw_payload_id?: number;
  archive_object_reference?: string;
  notes?: string;
}

export interface ImportantEvent extends ImportantEventPayload {
  id: number;
  created_at: string;
}

export interface OpsKpiMetricResponse {
  value: number | null;
  status: KpiStatus;
  numerator?: number | null;
  denominator?: number | null;
  unit?: string | null;
  window: string;
  details: Record<string, unknown>;
}

export interface OpsKpiResponse {
  gate_id: string;
  overall_status: KpiStatus;
  metrics: Record<string, OpsKpiMetricResponse>;
}

export interface ResearchGateArtifactResponse {
  status: KpiStatus;
  details: Record<string, unknown>;
}

export interface ResearchPhaseGateResponse {
  gate_id: string;
  verification_gate_id: string;
  overall_status: KpiStatus;
  metrics: Record<string, OpsKpiMetricResponse>;
  artifacts: Record<string, ResearchGateArtifactResponse>;
  missing_reasons: string[];
}
