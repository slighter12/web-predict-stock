export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: {
      fields?: Array<{
        field: string;
        code: string;
        reason: string;
      }>;
    };
  };
  meta?: {
    request_id?: string;
    run_id?: string;
  };
}

export interface AppError {
  status: number;
  code: string;
  message: string;
  requestId: string | null;
  runId?: string | null;
  details?: ApiErrorPayload["error"]["details"];
}
