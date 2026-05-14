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
  TwCompanyProfile,
  TwDailyReadinessRequest,
  TwDailyReadinessResponse,
} from "../types";

import { requestJson, requestJsonWithHeaders } from "./client";

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

const TW_COMPANY_PROFILE_PAGE_SIZE = 5000;

export const fetchTwCompanyProfiles = async (
  limit = TW_COMPANY_PROFILE_PAGE_SIZE,
  offset = 0,
) => {
  const firstPage = await requestJsonWithHeaders<TwCompanyProfile[]>(
    `/api/v1/data/tw-company-profiles?limit=${limit}&offset=${offset}`,
  );
  const totalCountHeader = firstPage.headers.get("X-Total-Count");
  const totalCount = totalCountHeader ? Number(totalCountHeader) : null;
  if (
    totalCount === null ||
    !Number.isFinite(totalCount)
  ) {
    if (firstPage.data.length < limit) {
      return firstPage.data;
    }

    const pages = [firstPage.data];
    let nextOffset = offset + limit;
    let nextPage: TwCompanyProfile[];
    do {
      nextPage = await requestJson<TwCompanyProfile[]>(
        `/api/v1/data/tw-company-profiles?limit=${limit}&offset=${nextOffset}`,
      );
      pages.push(nextPage);
      nextOffset += limit;
    } while (nextPage.length === limit);
    return pages.flat();
  }

  if (
    offset + firstPage.data.length >= totalCount
  ) {
    return firstPage.data;
  }

  const pages = [firstPage.data];
  for (
    let nextOffset = offset + Math.max(firstPage.data.length, limit);
    nextOffset < totalCount;
    nextOffset += limit
  ) {
    pages.push(
      await requestJson<TwCompanyProfile[]>(
        `/api/v1/data/tw-company-profiles?limit=${limit}&offset=${nextOffset}`,
      ),
    );
  }
  return pages.flat();
};

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
