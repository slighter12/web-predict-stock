import type {
  AdaptiveMode,
  BaselineName,
  DefaultBundleVersion,
  ExecutionRoute,
  MarketCode,
  ModelType,
  ReturnTarget,
  RuntimeMode,
  ValidationMethod,
} from "./common";
import type { ResearchFeatureRow } from "./forms";

export type PredictionFeatureModuleId =
  | "technical_indicators"
  | "factor_catalog"
  | "external_signals"
  | "peer_context";

export interface PredictionFeatureModulePreset {
  id: PredictionFeatureModuleId;
  label: string;
  description: string;
  helper: string;
}

export interface PredictionPipelineDataStage {
  market: MarketCode;
  symbolsInput: string;
  startDate: string;
  endDate: string;
  returnTarget: ReturnTarget;
  horizonDays: number;
}

export interface PredictionPipelineFeatureStage {
  selectedModuleIds: PredictionFeatureModuleId[];
  indicatorRows: ResearchFeatureRow[];
  factorCatalogVersion: string;
  scoringFactorIdsInput: string;
  externalSignalPolicyVersion: string;
  clusterSnapshotVersion: string;
  peerPolicyVersion: string;
}

export interface PredictionPipelineModelStage {
  modelType: ModelType;
  runtimeMode: RuntimeMode;
  defaultBundleVersion: DefaultBundleVersion | null;
  threshold: number | null;
  topN: number | null;
  allowProactiveSells: boolean;
}

export interface PredictionPipelineValidationStage {
  enableValidation: boolean;
  validationMethod: ValidationMethod;
  validationSplits: number;
  validationTestSize: number;
  baselines: BaselineName[];
  executionRoute: ExecutionRoute;
  slippage: number;
  fees: number;
  portfolioAum: number | null;
  recordAsMonitorRun: boolean;
  simulationProfileId: string;
  liveControlProfileId: string;
  manualConfirmed: boolean;
  adaptiveMode: AdaptiveMode;
  adaptiveProfileId: string;
  rewardDefinitionVersion: string;
  stateDefinitionVersion: string;
  rolloutControlVersion: string;
}

export interface PredictionPipelineDraft {
  data: PredictionPipelineDataStage;
  feature: PredictionPipelineFeatureStage;
  model: PredictionPipelineModelStage;
  validation: PredictionPipelineValidationStage;
}
