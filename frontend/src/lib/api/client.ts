import type { ApiErrorPayload, AppError } from "../types";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error implements AppError {
  status: number;
  code: string;
  requestId: string | null;
  runId?: string | null;
  details?: ApiErrorPayload["error"]["details"];

  constructor({ status, code, message, requestId, runId, details }: AppError) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.runId = runId;
    this.details = details;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-Id");
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return new ApiError({
      status: response.status,
      code: payload.error?.code ?? "UNKNOWN_ERROR",
      message: payload.error?.message ?? "Request failed.",
      requestId: payload.meta?.request_id ?? requestId,
      runId: payload.meta?.run_id ?? null,
      details: payload.error?.details,
    });
  } catch {
    return new ApiError({
      status: response.status,
      code: "UNKNOWN_ERROR",
      message: "Request failed.",
      requestId,
      runId: null,
    });
  }
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const bodyIsFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  const hasBody = init?.body !== undefined && init?.body !== null;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(hasBody && !bodyIsFormData
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}
