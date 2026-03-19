import type {
  DataIngestionRequest,
  DataIngestionResponse,
  ImportantEvent,
  ImportantEventPayload,
  LifecycleRecord,
  LifecycleRecordPayload,
  RecoveryDrillRecord,
  RecoveryDrillRequest,
  ReplayRecord,
  ReplayRequest,
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

export const fetchReplays = () => requestJson<ReplayRecord[]>("/api/v1/data/replays");

export const createRecoveryDrill = (payload: RecoveryDrillRequest) =>
  requestJson<RecoveryDrillRecord>("/api/v1/data/recovery-drills", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchRecoveryDrills = () =>
  requestJson<RecoveryDrillRecord[]>("/api/v1/data/recovery-drills");

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
