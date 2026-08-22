import type {
  ResearchFeatureDefinition,
  ResearchFeatureRow,
  ResearchFeatureRegistryResponse,
} from "../types";
import { toFeatureName } from "../types";

export const FEATURE_SOURCE_OPTIONS: ResearchFeatureRow["source"][] = [
  "open",
  "high",
  "low",
  "close",
  "volume",
];

export const FEATURE_REGISTRY_VERSION = "technical_feature_registry_v3";

export const FEATURE_REGISTRY_QUERY_KEY = [
  "research",
  "feature-registry",
] as const;

export const createFeatureRegistryQueryOptions = (
  queryFn: () => Promise<ResearchFeatureRegistryResponse>,
) => ({
  queryKey: FEATURE_REGISTRY_QUERY_KEY,
  queryFn,
  retry: 2,
  refetchOnWindowFocus: false,
});

// Keep this fallback declarative and aligned with the backend registry. The
// backend endpoint remains authoritative whenever it is available.
export const FALLBACK_FEATURE_DEFINITIONS: ResearchFeatureDefinition[] = [
  {
    name: "ma",
    family: "ma",
    label: "Moving Average",
    description: "Simple moving average for baseline trend smoothing.",
    default_window: 5,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 5 },
    required_columns: [],
  },
  {
    name: "ema",
    family: "ema",
    label: "Exponential Moving Average",
    description:
      "Faster trend-following average that reacts more quickly to recent data.",
    default_window: 5,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 5 },
    required_columns: [],
  },
  {
    name: "rsi",
    family: "rsi",
    label: "Relative Strength Index",
    description: "Momentum oscillator for overbought and oversold regimes.",
    default_window: 14,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 14 },
    required_columns: [],
  },
  {
    name: "roc",
    family: "roc",
    label: "Rate Of Change",
    description:
      "Windowed percent change for momentum and breakout-style signals.",
    default_window: 10,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 10 },
    required_columns: [],
  },
  {
    name: "volatility",
    family: "volatility",
    label: "Rolling Volatility",
    description:
      "Annualized rolling standard deviation of returns for risk-sensitive models.",
    default_window: 20,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 20 },
    required_columns: [],
  },
  {
    name: "zscore",
    family: "zscore",
    label: "Rolling Z-Score",
    description:
      "Normalized distance from the rolling mean for mean-reversion style features.",
    default_window: 20,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    parameter_tuple: { window: 20 },
    required_columns: [],
  },
  {
    name: "macd_line",
    family: "macd",
    label: "MACD Line",
    description: "Moving Average Convergence Divergence line.",
    default_window: 26,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: {
      fast_window: 12,
      slow_window: 26,
      signal_window: 9,
      macd_ewm: true,
      signal_ewm: true,
    },
    required_columns: ["close"],
  },
  {
    name: "macd_signal",
    family: "macd",
    label: "MACD Signal",
    description: "Signal line derived from the MACD line.",
    default_window: 26,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: {
      fast_window: 12,
      slow_window: 26,
      signal_window: 9,
      macd_ewm: true,
      signal_ewm: true,
    },
    required_columns: ["close"],
  },
  {
    name: "macd_histogram",
    family: "macd",
    label: "MACD Histogram",
    description: "Difference between the MACD line and signal line.",
    default_window: 26,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: {
      fast_window: 12,
      slow_window: 26,
      signal_window: 9,
      macd_ewm: true,
      signal_ewm: true,
    },
    required_columns: ["close"],
  },
  {
    name: "bbands_upper",
    family: "bbands",
    label: "Bollinger Upper Band",
    description:
      "Upper Bollinger Band using the conventional two-standard-deviation multiplier.",
    default_window: 20,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 20, alpha: 2, ewm: false },
    required_columns: ["close"],
  },
  {
    name: "bbands_middle",
    family: "bbands",
    label: "Bollinger Middle Band",
    description: "Rolling Bollinger middle band.",
    default_window: 20,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 20, alpha: 2, ewm: false },
    required_columns: ["close"],
  },
  {
    name: "bbands_lower",
    family: "bbands",
    label: "Bollinger Lower Band",
    description:
      "Lower Bollinger Band using the conventional two-standard-deviation multiplier.",
    default_window: 20,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 20, alpha: 2, ewm: false },
    required_columns: ["close"],
  },
  {
    name: "atr",
    family: "atr",
    label: "Average True Range",
    description:
      "Wilder-smoothed true range over the conventional 14-period window, seeded with the first 14 true ranges.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: {
      window: 14,
      smoothing_method: "wilder",
      seed_policy: "sma_first_window_true_ranges",
    },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "stoch_k",
    family: "stoch",
    label: "Stochastic %K",
    description: "Fast stochastic oscillator %K line.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { k_window: 14, d_window: 3, d_ewm: false },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "stoch_d",
    family: "stoch",
    label: "Stochastic %D",
    description: "Smoothed stochastic oscillator %D line.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { k_window: 14, d_window: 3, d_ewm: false },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "obv",
    family: "obv",
    label: "On-Balance Volume",
    description:
      "Cumulative volume signed by close-to-close direction; window 1 is a fixed compatibility sentinel.",
    default_window: 1,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 1 },
    required_columns: ["close", "volume"],
  },
  {
    name: "adx",
    family: "adx_dmi",
    label: "Average Directional Index",
    description:
      "Wilder-smoothed trend-strength component of directional movement.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 14 },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "dmi_plus",
    family: "adx_dmi",
    label: "Positive Directional Movement",
    description:
      "Positive directional indicator component paired with ADX.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 14 },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "dmi_minus",
    family: "adx_dmi",
    label: "Negative Directional Movement",
    description:
      "Negative directional indicator component paired with ADX.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 14 },
    required_columns: ["high", "low", "close"],
  },
  {
    name: "mfi",
    family: "mfi",
    label: "Money Flow Index",
    description:
      "Volume-weighted money-flow oscillator requiring 14 valid price movements per warmup segment.",
    default_window: 14,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 14, warmup_policy: "14_movements" },
    required_columns: ["high", "low", "close", "volume"],
  },
  {
    name: "cmf",
    family: "cmf",
    label: "Chaikin Money Flow",
    description:
      "Rolling money-flow volume ratio over the conventional 20-period window.",
    default_window: 20,
    window_editable: false,
    allowed_sources: ["close"],
    parameter_tuple: { window: 20 },
    required_columns: ["high", "low", "close", "volume"],
  },
];

const fallbackDefinitionByName = new Map(
  FALLBACK_FEATURE_DEFINITIONS.map((definition) => [
    definition.name,
    definition,
  ]),
);

export const getDefaultFeatureWindow = (name: ResearchFeatureRow["name"]) =>
  fallbackDefinitionByName.get(name)?.default_window ?? 14;

export const getPreferredFeatureSource = (
  allowedSources: ResearchFeatureRow["source"][],
): ResearchFeatureRow["source"] =>
  allowedSources.includes("close") ? "close" : (allowedSources[0] ?? "close");

export const buildFallbackFeatureDefinition = (
  name: ResearchFeatureRow["name"],
): ResearchFeatureDefinition => {
  const catalogDefinition = fallbackDefinitionByName.get(name);
  if (catalogDefinition) {
    return catalogDefinition;
  }

  const defaultWindow = getDefaultFeatureWindow(name);
  return {
    name,
    label: name.toUpperCase(),
    description: "",
    default_window: defaultWindow,
    window_editable: true,
    allowed_sources: FEATURE_SOURCE_OPTIONS,
    family: name,
    parameter_tuple: { window: defaultWindow },
    required_columns: [],
  };
};

export const getFeatureDefinitions = (
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) => (registryFeatures?.length ? registryFeatures : FALLBACK_FEATURE_DEFINITIONS);

export const getFeatureDefinitionGroups = (
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) => {
  const groups = new Map<string, ResearchFeatureDefinition[]>();
  for (const definition of getFeatureDefinitions(registryFeatures)) {
    const family = definition.family?.trim() || definition.name;
    const features = groups.get(family) ?? [];
    features.push(definition);
    groups.set(family, features);
  }
  return [...groups.entries()].map(([family, features]) => ({
    family,
    features,
  }));
};

export const getFeatureDefinition = (
  name: ResearchFeatureRow["name"],
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) =>
  getFeatureDefinitions(registryFeatures).find((feature) => feature.name === name) ??
  buildFallbackFeatureDefinition(name);

export const getAllowedSources = (
  name: ResearchFeatureRow["name"],
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) => {
  const definition = getFeatureDefinition(name, registryFeatures);
  return definition.allowed_sources.length
    ? definition.allowed_sources
    : FEATURE_SOURCE_OPTIONS;
};

export const resolveDefaultFeatureWindow = (
  name: ResearchFeatureRow["name"],
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) => getFeatureDefinition(name, registryFeatures).default_window;

export const isFeatureWindowEditable = (
  definition: ResearchFeatureDefinition,
) => definition.window_editable ?? true;

export const formatFeatureFamily = (family: string) =>
  family.replace(/_/g, " ").toUpperCase();

export const formatFeaturePreset = (
  definition: ResearchFeatureDefinition,
) => {
  const parameters = Object.entries(definition.parameter_tuple ?? {});
  if (!parameters.length) {
    return `window=${definition.default_window}`;
  }
  return parameters
    .map(([key, value]) => `${key.replace(/_/g, " ")}=${String(value)}`)
    .join(", ");
};

export const createIndicatorRow = (
  id: string,
  registryFeatures: ResearchFeatureDefinition[] | undefined,
): ResearchFeatureRow => {
  const defaultFeature =
    getFeatureDefinitions(registryFeatures)[0] ?? buildFallbackFeatureDefinition("ma");

  return {
    id,
    name: toFeatureName(defaultFeature.name),
    window: defaultFeature.default_window,
    source: getPreferredFeatureSource(defaultFeature.allowed_sources),
    shift: 1,
  };
};

export const updateIndicatorFeatureName = (
  feature: ResearchFeatureRow,
  nextNameValue: string,
  registryFeatures: ResearchFeatureDefinition[] | undefined,
): ResearchFeatureRow => {
  const nextName = toFeatureName(nextNameValue);
  const currentDefinition = getFeatureDefinition(feature.name, registryFeatures);
  const nextDefinition = getFeatureDefinition(nextName, registryFeatures);
  const nextSources = getAllowedSources(nextName, registryFeatures);
  const nextWindow = isFeatureWindowEditable(nextDefinition)
    ? feature.window === currentDefinition.default_window
      ? nextDefinition.default_window
      : feature.window
    : nextDefinition.default_window;

  return {
    ...feature,
    name: nextName,
    source: nextSources.includes(feature.source)
      ? feature.source
      : getPreferredFeatureSource(nextSources),
    window: nextWindow,
  };
};
