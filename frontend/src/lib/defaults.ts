import type { BaselineName, DashboardFormState, FeatureName, PriceSource } from "./types";

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
  market: "TW",
  symbolsInput: "2330",
  startDate: "2019-01-01",
  endDate: "2024-01-01",
  returnTarget: "open_to_open",
  horizonDays: 1,
  features: [defaultFeature(0, "ma"), defaultFeature(1, "rsi")],
  threshold: 0.003,
  topN: 5,
  allowProactiveSells: true,
  slippage: 0.001,
  fees: 0.002,
  enableValidation: true,
  validationMethod: "walk_forward",
  validationSplits: 3,
  validationTestSize: 0.2,
  baselines: ["buy_and_hold", "naive_momentum"],
});
