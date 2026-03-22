import type { ExecutionOrderRecord, KillSwitchRecord } from "../types";

import { requestJson } from "./client";

export const createSimulationOrder = (payload: {
  run_id?: string;
  market: string;
  symbol: string;
  side: string;
  quantity: number;
  requested_price?: number;
  simulation_profile_id?: string;
}) =>
  requestJson<ExecutionOrderRecord>("/api/v1/execution/simulation-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchSimulationReadbacks = () =>
  requestJson<ExecutionOrderRecord[]>("/api/v1/execution/simulation-readbacks");

export const createLiveOrder = (payload: {
  run_id?: string;
  market: string;
  symbol: string;
  side: string;
  quantity: number;
  requested_price?: number;
  live_control_profile_id?: string;
  manual_confirmed: boolean;
}) =>
  requestJson<ExecutionOrderRecord>("/api/v1/execution/live-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchLiveOrders = () =>
  requestJson<ExecutionOrderRecord[]>("/api/v1/execution/live-orders");

export const createKillSwitch = (payload: {
  scope_type: string;
  market?: string;
  is_enabled: boolean;
  reason?: string;
}) =>
  requestJson<KillSwitchRecord>("/api/v1/execution/live-controls/kill-switch", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchKillSwitchEvents = () =>
  requestJson<KillSwitchRecord[]>(
    "/api/v1/execution/live-controls/kill-switch",
  );
