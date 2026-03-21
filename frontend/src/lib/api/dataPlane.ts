import type {
  DataIngestionRequest,
  DataIngestionResponse,
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
  TickArchiveDispatchRequest,
  TickArchiveImportResponse,
  TickArchiveObjectRecord,
  TickArchiveRunRecord,
  TickOpsKpiResponse,
  TickReplayRecord,
  TickReplayRequest,
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
  return requestJson<TickArchiveImportResponse>("/api/v1/data/tick-archive-imports", {
    method: "POST",
    body: formData,
  });
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
