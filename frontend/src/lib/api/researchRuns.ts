import type {
  AdaptiveProfileRecord,
  AdaptiveTrainingRunRecord,
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

export const fetchResearchGate = (
  phase: "p3" | "p7" | "p8" | "p9" | "p10" | "p11",
) => requestJson<ResearchPhaseGateResponse>(`/api/v1/research/gates/${phase}`);

export const createAdaptiveProfile = (payload: {
  id: string;
  market: string;
  reward_definition_version: string;
  state_definition_version: string;
  rollout_control_version: string;
  notes?: string;
  rollout_detail?: Record<string, unknown>;
}) =>
  requestJson<AdaptiveProfileRecord>("/api/v1/research/adaptive-profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchAdaptiveProfiles = () =>
  requestJson<AdaptiveProfileRecord[]>("/api/v1/research/adaptive-profiles");

export const createAdaptiveTrainingRun = (payload: {
  adaptive_profile_id: string;
  market: string;
  adaptive_mode: string;
  reward_definition_version: string;
  state_definition_version: string;
  rollout_control_version: string;
  run_id?: string;
}) =>
  requestJson<AdaptiveTrainingRunRecord>(
    "/api/v1/research/adaptive-training-runs",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const fetchAdaptiveTrainingRuns = () =>
  requestJson<AdaptiveTrainingRunRecord[]>(
    "/api/v1/research/adaptive-training-runs",
  );
