import {
  FALLBACK_FEATURE_DEFINITIONS,
  FEATURE_REGISTRY_VERSION,
  formatFeaturePreset,
  getFeatureDefinitionGroups,
  updateIndicatorFeatureName,
} from "../src/lib/state/featureRegistry";

const assert: (
  condition: unknown,
  message: string,
) => asserts condition = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const expectedNames = new Set([
  "ma",
  "ema",
  "rsi",
  "roc",
  "volatility",
  "zscore",
  "macd_line",
  "macd_signal",
  "macd_histogram",
  "bbands_upper",
  "bbands_middle",
  "bbands_lower",
  "atr",
  "stoch_k",
  "stoch_d",
  "obv",
  "adx",
  "dmi_plus",
  "dmi_minus",
  "mfi",
  "cmf",
]);
const expectedFamilies: Record<string, string> = {
  ma: "ma",
  ema: "ema",
  rsi: "rsi",
  roc: "roc",
  volatility: "volatility",
  zscore: "zscore",
  macd_line: "macd",
  macd_signal: "macd",
  macd_histogram: "macd",
  bbands_upper: "bbands",
  bbands_middle: "bbands",
  bbands_lower: "bbands",
  atr: "atr",
  stoch_k: "stoch",
  stoch_d: "stoch",
  obv: "obv",
  adx: "adx_dmi",
  dmi_plus: "adx_dmi",
  dmi_minus: "adx_dmi",
  mfi: "mfi",
  cmf: "cmf",
};

assert(
  FEATURE_REGISTRY_VERSION === "technical_feature_registry_v3",
  "fallback registry version drifted",
);
assert(
  new Set(FALLBACK_FEATURE_DEFINITIONS.map((definition) => definition.name)).size ===
    expectedNames.size,
  "fallback feature names must be unique",
);
assert(
  FALLBACK_FEATURE_DEFINITIONS.every((definition) =>
    expectedNames.has(definition.name),
  ),
  "fallback contains an unknown feature",
);
for (const definition of FALLBACK_FEATURE_DEFINITIONS) {
  assert(
    definition.family === expectedFamilies[definition.name],
    `${definition.name} family drifted`,
  );
}

const macd = FALLBACK_FEATURE_DEFINITIONS.find(
  (definition) => definition.name === "macd_line",
);
assert(macd, "MACD fallback definition is missing");
assert(macd.family === "macd", "MACD family drifted");
assert(macd.window_editable === false, "MACD window must be fixed");
assert(
  formatFeaturePreset(macd) ===
    "fast window=12, slow window=26, signal window=9, macd ewm=true, signal ewm=true",
  "MACD preset formatter drifted",
);
assert(
  JSON.stringify(macd.parameter_tuple) ===
    JSON.stringify({
      fast_window: 12,
      slow_window: 26,
      signal_window: 9,
      macd_ewm: true,
      signal_ewm: true,
    }),
  "MACD parameter tuple drifted",
);

const atr = FALLBACK_FEATURE_DEFINITIONS.find(
  (definition) => definition.name === "atr",
);
assert(atr, "ATR fallback definition is missing");
assert(
  JSON.stringify(atr.parameter_tuple) ===
    JSON.stringify({
      window: 14,
      smoothing_method: "wilder",
      seed_policy: "sma_first_window_true_ranges",
    }),
  "ATR parameter tuple drifted",
);

const mfi = FALLBACK_FEATURE_DEFINITIONS.find(
  (definition) => definition.name === "mfi",
);
assert(mfi, "MFI fallback definition is missing");
assert(
  mfi.parameter_tuple?.warmup_policy === "14_movements",
  "MFI warmup policy drifted",
);

const groups = getFeatureDefinitionGroups(undefined);
assert(
  groups.find((group) => group.family === "macd")?.features.length === 3,
  "MACD outputs must share a family group",
);

const updated = updateIndicatorFeatureName(
  {
    id: "feature-1",
    name: "ma",
    window: 10,
    source: "close",
    shift: 1,
  },
  "macd_line",
  undefined,
);
assert(updated.window === 26, "fixed feature switch must reset its window");

console.log("feature registry smoke test passed");
