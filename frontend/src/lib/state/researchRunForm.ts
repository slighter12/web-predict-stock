import type {
  BaselineName,
  DefaultBundleVersion,
  ResearchRunCreateRequest,
  ResearchRunFormState,
  ResearchFeatureRow,
  RuntimeMode,
} from "../types";

export const DEFAULT_RUNTIME_MODE: RuntimeMode = "runtime_compatibility_mode";
export const VNEXT_SPEC_MODE: RuntimeMode = "vnext_spec_mode";
export const DEFAULT_BUNDLE_VERSION: DefaultBundleVersion = "research_spec_v1";
export const DEFAULT_THRESHOLD = 0.003;
export const DEFAULT_TOP_N = 5;
export const SPEC_BUNDLE_THRESHOLD = 0.01;
export const SPEC_BUNDLE_TOP_N = 10;
export const DEFAULT_MONITOR_PROFILE_ID = "p3_monitor_default_v1" as const;

const defaultFeature = (
  index = 0,
  name: ResearchFeatureRow["name"] = "ma",
  source: ResearchFeatureRow["source"] = "close",
): ResearchFeatureRow => ({
  id: `feature-${index + 1}`,
  name,
  window: name === "ma" ? 5 : 14,
  source,
  shift: 1,
});

export const availableBaselines: BaselineName[] = [
  "buy_and_hold",
  "naive_momentum",
  "ma_crossover",
];

export const createDefaultResearchRunFormState = (): ResearchRunFormState => ({
  runtimeMode: DEFAULT_RUNTIME_MODE,
  defaultBundleVersion: null,
  market: "TW",
  symbolsInput: "2330",
  startDate: "2019-01-01",
  endDate: "2024-01-01",
  returnTarget: "open_to_open",
  horizonDays: 1,
  features: [defaultFeature(0, "ma"), defaultFeature(1, "rsi")],
  threshold: DEFAULT_THRESHOLD,
  topN: DEFAULT_TOP_N,
  allowProactiveSells: true,
  slippage: 0.001,
  fees: 0.002,
  portfolioAum: null,
  recordAsMonitorRun: false,
  enableValidation: true,
  validationMethod: "walk_forward",
  validationSplits: 3,
  validationTestSize: 0.2,
  baselines: ["buy_and_hold", "naive_momentum"],
});

export const parseOptionalNumber = (value: string): number | null => {
  if (value.trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export const parseSymbols = (symbolsInput: string) =>
  symbolsInput
    .split(",")
    .map((symbol) => symbol.trim())
    .filter(Boolean);

export const buildResearchRunPayload = (
  form: ResearchRunFormState,
): ResearchRunCreateRequest => {
  const strategy: ResearchRunCreateRequest["strategy"] = {
    type: "research_v1",
    allow_proactive_sells: form.allowProactiveSells,
  };
  if (form.threshold !== null) {
    strategy.threshold = form.threshold;
  }
  if (form.topN !== null) {
    strategy.top_n = form.topN;
  }

  return {
    runtime_mode: form.runtimeMode,
    default_bundle_version:
      form.runtimeMode === VNEXT_SPEC_MODE
        ? (form.defaultBundleVersion ?? undefined)
        : undefined,
    market: form.market,
    symbols: parseSymbols(form.symbolsInput),
    date_range: {
      start: form.startDate,
      end: form.endDate,
    },
    return_target: form.returnTarget,
    horizon_days: form.horizonDays,
    features: form.features.map((feature) => ({
      name: feature.name,
      window: feature.window,
      source: feature.source,
      shift: feature.shift,
    })),
    model: {
      type: "xgboost",
      params: {},
    },
    strategy,
    execution: {
      slippage: form.slippage,
      fees: form.fees,
    },
    portfolio_aum: form.portfolioAum ?? undefined,
    monitor_profile_id: form.recordAsMonitorRun
      ? DEFAULT_MONITOR_PROFILE_ID
      : undefined,
    validation: form.enableValidation
      ? {
          method: form.validationMethod,
          splits: form.validationSplits,
          test_size: form.validationTestSize,
        }
      : undefined,
    baselines: form.baselines,
  };
};
