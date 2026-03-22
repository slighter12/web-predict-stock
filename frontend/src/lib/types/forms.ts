import type {
  AdaptiveMode,
  BaselineName,
  DefaultBundleVersion,
  ExecutionRoute,
  FeatureName,
  MarketCode,
  PriceSource,
  ReturnTarget,
  RuntimeMode,
  ValidationMethod,
} from "./common";

export interface ResearchFeatureRow {
  id: string;
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface ResearchRunFormState {
  runtimeMode: RuntimeMode;
  defaultBundleVersion: DefaultBundleVersion | null;
  market: MarketCode;
  symbolsInput: string;
  startDate: string;
  endDate: string;
  returnTarget: ReturnTarget;
  horizonDays: number;
  features: ResearchFeatureRow[];
  threshold: number | null;
  topN: number | null;
  allowProactiveSells: boolean;
  slippage: number;
  fees: number;
  portfolioAum: number | null;
  recordAsMonitorRun: boolean;
  enableValidation: boolean;
  validationMethod: ValidationMethod;
  validationSplits: number;
  validationTestSize: number;
  baselines: BaselineName[];
  factorCatalogVersion: string;
  scoringFactorIdsInput: string;
  externalSignalPolicyVersion: string;
  clusterSnapshotVersion: string;
  peerPolicyVersion: string;
  executionRoute: ExecutionRoute;
  simulationProfileId: string;
  liveControlProfileId: string;
  manualConfirmed: boolean;
  adaptiveMode: AdaptiveMode;
  adaptiveProfileId: string;
  rewardDefinitionVersion: string;
  stateDefinitionVersion: string;
  rolloutControlVersion: string;
}
