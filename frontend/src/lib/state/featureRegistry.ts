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

export const getDefaultFeatureWindow = (name: ResearchFeatureRow["name"]) => {
  switch (name) {
    case "ma":
    case "ema":
      return 5;
    case "rsi":
      return 14;
    case "roc":
      return 10;
    case "volatility":
    case "zscore":
      return 20;
  }

  return 14;
};

export const getPreferredFeatureSource = (
  allowedSources: ResearchFeatureRow["source"][],
): ResearchFeatureRow["source"] =>
  allowedSources.includes("close") ? "close" : (allowedSources[0] ?? "close");

export const buildFallbackFeatureDefinition = (
  name: ResearchFeatureRow["name"],
): ResearchFeatureDefinition => ({
  name,
  label: name.toUpperCase(),
  description: "",
  default_window: getDefaultFeatureWindow(name),
  allowed_sources: FEATURE_SOURCE_OPTIONS,
});

export const FALLBACK_FEATURE_DEFINITIONS: ResearchFeatureDefinition[] = [
  {
    name: "ma",
    label: "Moving Average",
    description: "Simple moving average for baseline trend smoothing.",
    default_window: getDefaultFeatureWindow("ma"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
  {
    name: "ema",
    label: "Exponential Moving Average",
    description:
      "Faster trend-following average that reacts more quickly to recent data.",
    default_window: getDefaultFeatureWindow("ema"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
  {
    name: "rsi",
    label: "Relative Strength Index",
    description: "Momentum oscillator for overbought and oversold regimes.",
    default_window: getDefaultFeatureWindow("rsi"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
  {
    name: "roc",
    label: "Rate Of Change",
    description:
      "Windowed percent change for momentum and breakout-style signals.",
    default_window: getDefaultFeatureWindow("roc"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
  {
    name: "volatility",
    label: "Rolling Volatility",
    description:
      "Annualized rolling standard deviation of returns for risk-sensitive models.",
    default_window: getDefaultFeatureWindow("volatility"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
  {
    name: "zscore",
    label: "Rolling Z-Score",
    description:
      "Normalized distance from the rolling mean for mean-reversion style features.",
    default_window: getDefaultFeatureWindow("zscore"),
    allowed_sources: FEATURE_SOURCE_OPTIONS,
  },
];

export const getFeatureDefinitions = (
  registryFeatures: ResearchFeatureDefinition[] | undefined,
) => (registryFeatures?.length ? registryFeatures : FALLBACK_FEATURE_DEFINITIONS);

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
) => getFeatureDefinition(name, registryFeatures).default_window ?? getDefaultFeatureWindow(name);

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
  const nextSources = getAllowedSources(nextName, registryFeatures);

  return {
    ...feature,
    name: nextName,
    source: nextSources.includes(feature.source)
      ? feature.source
      : getPreferredFeatureSource(nextSources),
    window:
      feature.window === resolveDefaultFeatureWindow(feature.name, registryFeatures)
        ? resolveDefaultFeatureWindow(nextName, registryFeatures)
        : feature.window,
  };
};
