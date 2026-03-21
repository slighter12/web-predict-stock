import type { HealthResponse } from "../types";

import { requestJson } from "./client";

export const fetchSystemHealth = () =>
  requestJson<HealthResponse>("/api/v1/system/health");
