import type { ApiErrorPayload, AppError, BacktestRequest, BacktestResponse, HealthResponse } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error implements AppError {
  status: number;
  code: string;
  requestId: string | null;
  details?: ApiErrorPayload["error"]["details"];

  constructor({ status, code, message, requestId, details }: AppError) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

const buildRequestId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `req_${Date.now()}`;

async function parseError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-Id");
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return new ApiError({
      status: response.status,
      code: payload.error?.code ?? "UNKNOWN_ERROR",
      message: payload.error?.message ?? "Request failed.",
      requestId: payload.meta?.request_id ?? requestId,
      details: payload.error?.details,
    });
  } catch {
    return new ApiError({
      status: response.status,
      code: "UNKNOWN_ERROR",
      message: "Request failed.",
      requestId,
    });
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const requestId = buildRequestId();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": requestId,
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

export const fetchHealth = () => requestJson<HealthResponse>("/api/v1/health");

export const runBacktest = (payload: BacktestRequest) =>
  requestJson<BacktestResponse>("/api/v1/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
