export type MarketCode = "TW" | "US";
export type PriceSource = "open" | "high" | "low" | "close" | "volume";
export type FeatureName = "ma" | "rsi";
export type ReturnTarget = "open_to_open" | "close_to_close" | "open_to_close";
export type ValidationMethod = "holdout" | "walk_forward" | "rolling_window" | "expanding_window";
export type BaselineName = "buy_and_hold" | "naive_momentum" | "ma_crossover";

export interface FeatureSpec {
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface ValidationConfig {
  method: ValidationMethod;
  splits: number;
  test_size: number;
}

export interface BacktestRequest {
  market: MarketCode;
  symbols: string[];
  date_range: {
    start: string;
    end: string;
  };
  return_target: ReturnTarget;
  horizon_days: number;
  features: FeatureSpec[];
  model: {
    type: "xgboost";
    params: Record<string, never>;
  };
  strategy: {
    type: "research_v1";
    threshold: number;
    top_n: number;
    allow_proactive_sells: boolean;
  };
  execution: {
    slippage: number;
    fees: number;
  };
  validation?: ValidationConfig;
  baselines: BaselineName[];
}

export interface Metrics {
  total_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  turnover: number | null;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface SignalPoint {
  date: string;
  symbol: string;
  score: number;
  position: number;
}

export interface ValidationSummary {
  method: ValidationMethod;
  metrics: Record<string, number>;
}

export interface BacktestResponse {
  run_id: string;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
}

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
  };
}

export interface AppError {
  status: number;
  code: string;
  message: string;
  requestId: string | null;
  details?: ApiErrorPayload["error"]["details"];
}

export interface FormFeatureRow {
  id: string;
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface DashboardFormState {
  market: MarketCode;
  symbolsInput: string;
  startDate: string;
  endDate: string;
  returnTarget: ReturnTarget;
  horizonDays: number;
  features: FormFeatureRow[];
  threshold: number;
  topN: number;
  allowProactiveSells: boolean;
  slippage: number;
  fees: number;
  enableValidation: boolean;
  validationMethod: ValidationMethod;
  validationSplits: number;
  validationTestSize: number;
  baselines: BaselineName[];
}
