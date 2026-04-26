import type {
  ClusterSnapshotRecord,
  DataIngestionRequest,
  DataIngestionResponse,
  ExternalRawArchiveRecord,
  ExternalSignalAuditRecord,
  ExternalSignalRecord,
  FactorCatalogRecord,
  FactorMaterializationRecord,
  ImportantEvent,
  ImportantEventPayload,
  LifecycleRecord,
  LifecycleRecordPayload,
  RecoveryDrillRecord,
  RecoveryDrillRequest,
  RecoveryDrillScheduleRecord,
  RecoveryDrillScheduleRequest,
  ReplayRecord,
  ReplayRequest,
  PeerFeatureRunRecord,
  TickArchiveDispatchRequest,
  TickArchiveImportResponse,
  TickArchiveObjectRecord,
  TickArchiveRunRecord,
  TickOpsKpiResponse,
  TickReplayRecord,
  TickReplayRequest,
  TwDailyReadinessRequest,
  TwDailyReadinessResponse,
} from "../types";

import { requestJson } from "./client";

export const createDataIngestion = (payload: DataIngestionRequest) =>
  requestJson<DataIngestionResponse>("/api/v1/data/ingestions", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createReplay = (payload: ReplayRequest) =>
  requestJson<ReplayRecord>("/api/v1/data/replays", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchReplays = () =>
  requestJson<ReplayRecord[]>("/api/v1/data/replays");

export const fetchTwDailyReadiness = (payload: TwDailyReadinessRequest) =>
  requestJson<TwDailyReadinessResponse>("/api/v1/data/readiness/tw-daily", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const createRecoveryDrill = (payload: RecoveryDrillRequest) =>
  requestJson<RecoveryDrillRecord>("/api/v1/data/recovery-drills", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchRecoveryDrills = () =>
  requestJson<RecoveryDrillRecord[]>("/api/v1/data/recovery-drills");

export const createRecoveryDrillSchedule = (
  payload: RecoveryDrillScheduleRequest,
) =>
  requestJson<RecoveryDrillScheduleRecord>(
    "/api/v1/data/recovery-drill-schedules",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const fetchRecoveryDrillSchedules = () =>
  requestJson<RecoveryDrillScheduleRecord[]>(
    "/api/v1/data/recovery-drill-schedules",
  );

export const createLifecycleRecord = (payload: LifecycleRecordPayload) =>
  requestJson<LifecycleRecord>("/api/v1/data/lifecycle-records", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchLifecycleRecords = () =>
  requestJson<LifecycleRecord[]>("/api/v1/data/lifecycle-records");

export const createImportantEvent = (payload: ImportantEventPayload) =>
  requestJson<ImportantEvent>("/api/v1/data/important-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchImportantEvents = () =>
  requestJson<ImportantEvent[]>("/api/v1/data/important-events");

export const createTickArchiveDispatch = (
  payload: TickArchiveDispatchRequest,
) =>
  requestJson<TickArchiveRunRecord>("/api/v1/data/tick-archive-dispatches", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchTickArchiveDispatches = () =>
  requestJson<TickArchiveRunRecord[]>("/api/v1/data/tick-archive-dispatches");

export const createTickArchiveImport = ({
  market,
  trading_date,
  notes,
  archive_file,
}: {
  market: string;
  trading_date: string;
  notes?: string;
  archive_file: File;
}) => {
  const formData = new FormData();
  formData.append("market", market);
  formData.append("trading_date", trading_date);
  if (notes) {
    formData.append("notes", notes);
  }
  formData.append("archive_file", archive_file);
  return requestJson<TickArchiveImportResponse>(
    "/api/v1/data/tick-archive-imports",
    {
      method: "POST",
      body: formData,
    },
  );
};

export const fetchTickArchives = () =>
  requestJson<TickArchiveObjectRecord[]>("/api/v1/data/tick-archives");

export const createTickReplay = (payload: TickReplayRequest) =>
  requestJson<TickReplayRecord>("/api/v1/data/tick-replays", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchTickReplays = () =>
  requestJson<TickReplayRecord[]>("/api/v1/data/tick-replays");

export const fetchTickOpsKpis = () =>
  requestJson<TickOpsKpiResponse>("/api/v1/data/tick-ops/kpis");

export const createExternalSignalIngestion = (payload: {
  market: string;
  source_family: string;
  coverage_start: string;
  coverage_end: string;
  notes?: string;
}) =>
  requestJson<ExternalRawArchiveRecord>(
    "/api/v1/data/external-signal-ingestions",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const fetchExternalSignals = () =>
  requestJson<ExternalSignalRecord[]>("/api/v1/data/external-signals");

export const createExternalSignalAudit = (payload: {
  market: string;
  source_family: string;
  audit_window_start: string;
  audit_window_end: string;
}) =>
  requestJson<ExternalSignalAuditRecord>(
    "/api/v1/data/external-signal-audits",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const fetchExternalSignalAudits = () =>
  requestJson<ExternalSignalAuditRecord[]>(
    "/api/v1/data/external-signal-audits",
  );

export const createFactorCatalog = (payload: {
  id: string;
  market: string;
  source_family: string;
  lineage_version: string;
  minimum_coverage_ratio: number;
  is_active: boolean;
  notes?: string;
  entries: Array<{
    factor_id: string;
    display_name: string;
    formula_definition: string;
    lineage: string;
    timing_semantics: string;
    missing_value_policy: string;
    scoring_eligible: boolean;
  }>;
}) =>
  requestJson<FactorCatalogRecord>("/api/v1/data/factor-catalogs", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchFactorCatalogs = () =>
  requestJson<FactorCatalogRecord[]>("/api/v1/data/factor-catalogs");

export const fetchFactorMaterializations = (runId?: string) =>
  requestJson<FactorMaterializationRecord[]>(
    `/api/v1/data/factor-materializations${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`,
  );

export const createClusterSnapshot = (payload: {
  market: string;
  trading_date: string;
  snapshot_version: string;
  factor_catalog_version?: string;
  cluster_count: number;
  notes?: string;
}) =>
  requestJson<ClusterSnapshotRecord>("/api/v1/data/cluster-snapshots", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchClusterSnapshots = () =>
  requestJson<ClusterSnapshotRecord[]>("/api/v1/data/cluster-snapshots");

export const createPeerFeatureRun = (payload: {
  snapshot_id: number;
  peer_policy_version: string;
  symbol_limit: number;
}) =>
  requestJson<PeerFeatureRunRecord>("/api/v1/data/peer-feature-runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchPeerFeatureRuns = () =>
  requestJson<PeerFeatureRunRecord[]>("/api/v1/data/peer-feature-runs");
