import type {
  ResearchFeatureRegistryResponse,
  ResearchPhaseGateResponse,
  ResearchRunCreateRequest,
  ResearchRunRecord,
  ResearchRunResponse,
} from "../types";

import { requestJson } from "./client";

export const createResearchRun = (payload: ResearchRunCreateRequest) =>
  requestJson<ResearchRunResponse>("/api/v1/research/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchResearchRun = (runId: string) =>
  requestJson<ResearchRunRecord>(`/api/v1/research/runs/${runId}`);

export const fetchResearchRuns = () =>
  requestJson<ResearchRunRecord[]>("/api/v1/research/runs");

export const fetchResearchFeatureRegistry = () =>
  requestJson<ResearchFeatureRegistryResponse>("/api/v1/research/feature-registry");

export const fetchResearchGate = (phase: "p3") =>
  requestJson<ResearchPhaseGateResponse>(`/api/v1/research/gates/${phase}`);
