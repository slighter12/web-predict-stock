import type { FeatureName, PriceSource } from "./common";

export interface ResearchFeatureRow {
  id: string;
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}
