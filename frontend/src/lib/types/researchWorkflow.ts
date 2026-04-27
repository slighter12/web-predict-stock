import type {
  BaselineName,
  DefaultBundleVersion,
  RuntimeMode,
  ValidationMethod,
} from "./common";
import type { ResearchFeatureRow } from "./forms";

export type ResearchWorkflowStageId =
  | "universe"
  | "signal_sources"
  | "model_family"
  | "evaluation"
  | "review";

export type ResearchTemplateId = "baseline_research";

export type ResearchCapabilityId = "technical_indicators";

export type ResearchCapabilityStatus =
  | "available"
  | "setup_required"
  | "gated"
  | "not_implemented";

export type ModelFamilyId = "tree_ensemble" | "deep_learning";

export type ModelVariantId =
  | "xgboost"
  | "random_forest"
  | "extra_trees"
  | "lstm";

export interface ResearchUniverseStage {
  market: "TW";
  symbolsInput: string;
  startDate: string;
  endDate: string;
  returnTarget: "open_to_open" | "close_to_close" | "open_to_close";
  horizonDays: number;
}

export interface ResearchSignalSourceStage {
  indicatorRows: ResearchFeatureRow[];
}

export interface ResearchModelFamilyStage {
  familyId: ModelFamilyId;
  variantId: ModelVariantId;
  runtimeMode: RuntimeMode;
  defaultBundleVersion: DefaultBundleVersion | null;
  threshold: number | null;
  topN: number | null;
  allowProactiveSells: boolean;
}

export interface ResearchEvaluationStage {
  enableValidation: boolean;
  validationMethod: ValidationMethod;
  validationSplits: number;
  validationTestSize: number;
  baselines: BaselineName[];
  slippage: number;
  fees: number;
  portfolioAum: number | null;
  recordAsMonitorRun: boolean;
}

export interface ResearchWorkflowDraft {
  templateId: ResearchTemplateId;
  capabilities: Record<ResearchCapabilityId, boolean>;
  universe: ResearchUniverseStage;
  signalSources: ResearchSignalSourceStage;
  modelFamily: ResearchModelFamilyStage;
  evaluation: ResearchEvaluationStage;
}

export interface ResearchTemplatePreset {
  id: ResearchTemplateId;
  label: string;
  summary: string;
  defaultCapabilities: ResearchCapabilityId[];
  recommendedFamilyId: ModelFamilyId;
  recommendedVariantId: ModelVariantId;
}

export interface ResearchCapabilityDefinition {
  id: ResearchCapabilityId;
  label: string;
  stage: ResearchWorkflowStageId;
  status: ResearchCapabilityStatus;
  summary: string;
  requires: ResearchCapabilityId[];
  fields: string[];
  gateRefs: string[];
  requestMapping: string[];
}

export interface ModelVariantDefinition {
  id: ModelVariantId;
  label: string;
  summary: string;
  status: "available" | "not_implemented";
}

export interface ModelFamilyDefinition {
  id: ModelFamilyId;
  label: string;
  summary: string;
  status: "available" | "not_implemented";
  variantIds: ModelVariantId[];
}

export interface CapabilityReadinessState {
  capabilityId: ResearchCapabilityId;
  status: ResearchCapabilityStatus;
  summary: string;
  gateId: string | null;
  overallStatus: string | null;
}

export interface WorkflowValidationErrors {
  [key: string]: string;
}

export interface ResearchSubmissionSummary {
  templateId: ResearchTemplateId;
  templateLabel: string;
  modelFamilyId: ModelFamilyId;
  modelFamilyLabel: string;
  modelVariantId: ModelVariantId;
  modelVariantLabel: string;
  capabilityIds: ResearchCapabilityId[];
}
