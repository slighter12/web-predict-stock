import type {
  BaselineName,
  DashboardFormState,
  DefaultBundleVersion,
  FeatureName,
  PriceSource,
  RuntimeMode,
} from "./types";

export const DEFAULT_RUNTIME_MODE: RuntimeMode = "runtime_compatibility_mode";
export const VNEXT_SPEC_MODE: RuntimeMode = "vnext_spec_mode";
export const DEFAULT_BUNDLE_VERSION: DefaultBundleVersion = "research_spec_v1";
export const DEFAULT_THRESHOLD = 0.003;
export const DEFAULT_TOP_N = 5;
export const SPEC_BUNDLE_THRESHOLD = 0.01;
export const SPEC_BUNDLE_TOP_N = 10;

const defaultFeature = (index = 0, name: FeatureName = "ma", source: PriceSource = "close") => ({
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

export const createDefaultFormState = (): DashboardFormState => ({
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
  enableValidation: true,
  validationMethod: "walk_forward",
  validationSplits: 3,
  validationTestSize: 0.2,
  baselines: ["buy_and_hold", "naive_momentum"],
});
