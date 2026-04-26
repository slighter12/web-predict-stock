import type {
  CapabilityReadinessState,
  ModelFamilyDefinition,
  ModelFamilyId,
  ModelVariantDefinition,
  ModelVariantId,
  ResearchCapabilityDefinition,
  ResearchCapabilityId,
  ResearchCapabilityStatus,
  ResearchPhaseGateResponse,
  ResearchSubmissionSummary,
  ResearchTemplateId,
  ResearchTemplatePreset,
  ResearchWorkflowDraft,
  WorkflowValidationErrors,
  ResearchFeatureRow,
  ResearchRunCreateRequest,
  ResearchRunRecord,
  ResearchRunResponse,
} from "../types";
import {
  DEFAULT_BUNDLE_VERSION,
  DEFAULT_MONITOR_PROFILE_ID,
  DEFAULT_RUNTIME_MODE,
  DEFAULT_THRESHOLD,
  DEFAULT_TOP_N,
  VNEXT_SPEC_MODE,
  availableBaselines,
} from "./predictionPipeline";
import { getDefaultFeatureWindow } from "./featureRegistry";

const formatLocalDate = (date: Date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);

const createRecentDateRange = () => {
  const end = new Date();
  do {
    end.setDate(end.getDate() - 1);
  } while (end.getDay() === 0 || end.getDay() === 6);

  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);

  return {
    start: formatLocalDate(start),
    end: formatLocalDate(end),
  };
};

const defaultIndicator = (
  index = 0,
  name: ResearchFeatureRow["name"] = "ma",
  source: ResearchFeatureRow["source"] = "close",
): ResearchFeatureRow => ({
  id: `workflow-feature-${index + 1}`,
  name,
  window: getDefaultFeatureWindow(name),
  source,
  shift: 1,
});

const capabilityStatusRank: Record<ResearchCapabilityStatus, number> = {
  available: 0,
  setup_required: 1,
  gated: 2,
  not_implemented: 3,
};

export const researchTemplates: ResearchTemplatePreset[] = [
  {
    id: "baseline_research",
    label: "Baseline Study",
    summary:
      "TW daily features, tree regression, model diagnostics, baselines, and an offline backtest.",
    defaultCapabilities: ["technical_indicators"],
    recommendedFamilyId: "tree_ensemble",
    recommendedVariantId: "xgboost",
  },
];

export const researchCapabilityRegistry: ResearchCapabilityDefinition[] = [
  {
    id: "technical_indicators",
    label: "Technical Indicators",
    stage: "signal_sources",
    status: "available",
    summary:
      "Core tabular inputs for baseline research. This stays on by default so the run always has a structured feature frame.",
    requires: [],
    fields: ["indicatorRows"],
    gateRefs: [],
    requestMapping: ["features"],
  },
];

export const modelVariants: ModelVariantDefinition[] = [
  {
    id: "xgboost",
    label: "XGBoost",
    summary:
      "Default gradient-boosted tree path and the fastest way to a valid baseline run.",
    status: "available",
  },
  {
    id: "random_forest",
    label: "Random Forest",
    summary:
      "Bagging tree baseline for robustness checks and lower-variance comparisons.",
    status: "available",
  },
  {
    id: "extra_trees",
    label: "Extra Trees",
    summary:
      "A higher-randomness tree ensemble for quick comparison against the default boosted path.",
    status: "available",
  },
  {
    id: "lstm",
    label: "Sequence LSTM",
    summary:
      "Reserved for future deep-learning expansion. Visible in v2 but not yet implemented.",
    status: "not_implemented",
  },
];

export const modelFamilies: ModelFamilyDefinition[] = [
  {
    id: "tree_ensemble",
    label: "Tree Ensemble",
    summary:
      "Current production-ready family that maps cleanly to the existing backend run contract.",
    status: "available",
    variantIds: ["xgboost", "random_forest", "extra_trees"],
  },
  {
    id: "deep_learning",
    label: "Deep Learning",
    summary:
      "Future model-family expansion surface for sequence and representation learning. Visible but intentionally blocked for now.",
    status: "not_implemented",
    variantIds: ["lstm"],
  },
];

const createDefaultCapabilities = (): Record<
  ResearchCapabilityId,
  boolean
> => ({
  technical_indicators: true,
  factor_catalog: false,
  external_signals: false,
  peer_context: false,
  simulation_execution: false,
  adaptive_workflow: false,
});

export const parseSymbols = (symbolsInput: string) =>
  symbolsInput
    .split(",")
    .map((symbol) => symbol.trim())
    .filter(Boolean);

export const parseScoringFactorIds = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const getTemplateById = (templateId: ResearchTemplateId) =>
  researchTemplates.find((template) => template.id === templateId) ??
  researchTemplates[0];

export const getModelFamilyById = (familyId: ModelFamilyId) =>
  modelFamilies.find((family) => family.id === familyId) ?? modelFamilies[0];

export const getModelVariantById = (variantId: ModelVariantId) =>
  modelVariants.find((variant) => variant.id === variantId) ?? modelVariants[0];

export const getCapabilityDefinition = (capabilityId: ResearchCapabilityId) =>
  researchCapabilityRegistry.find(
    (capability) => capability.id === capabilityId,
  ) ?? researchCapabilityRegistry[0];

export const getAvailableVariantsForFamily = (familyId: ModelFamilyId) =>
  getModelFamilyById(familyId)
    .variantIds.map((variantId) => getModelVariantById(variantId))
    .filter((variant) => variant.status === "available");

export const createDefaultResearchWorkflowDraft = (
  templateId: ResearchTemplateId = "baseline_research",
): ResearchWorkflowDraft => {
  const dateRange = createRecentDateRange();
  const template = getTemplateById(templateId);
  const capabilities = createDefaultCapabilities();

  for (const capabilityId of template.defaultCapabilities) {
    capabilities[capabilityId] = true;
  }

  return {
    templateId: template.id,
    capabilities,
    universe: {
      market: "TW",
      symbolsInput: "2330",
      startDate: dateRange.start,
      endDate: dateRange.end,
      returnTarget: "open_to_open",
      horizonDays: 1,
    },
    signalSources: {
      indicatorRows: [defaultIndicator(0, "ma"), defaultIndicator(1, "rsi")],
      factorCatalogVersion: "",
      scoringFactorIdsInput: "",
      externalSignalPolicyVersion: "",
      clusterSnapshotVersion: "",
      peerPolicyVersion: "",
    },
    modelFamily: {
      familyId: template.recommendedFamilyId,
      variantId: template.recommendedVariantId,
      runtimeMode: DEFAULT_RUNTIME_MODE,
      defaultBundleVersion: null,
      threshold: DEFAULT_THRESHOLD,
      topN: DEFAULT_TOP_N,
      allowProactiveSells: true,
    },
    evaluation: {
      enableValidation: true,
      validationMethod: "walk_forward",
      validationSplits: 3,
      validationTestSize: 0.2,
      baselines: ["buy_and_hold", "naive_momentum"],
      executionRoute: "research_only",
      slippage: 0.001,
      fees: 0.002,
      portfolioAum: null,
      recordAsMonitorRun: false,
      simulationProfileId: "",
      liveControlProfileId: "",
      manualConfirmed: false,
      adaptiveMode: "off",
      adaptiveProfileId: "",
      rewardDefinitionVersion: "",
      stateDefinitionVersion: "",
      rolloutControlVersion: "",
    },
  };
};

const resetCapabilityFields = (
  draft: ResearchWorkflowDraft,
  capabilityId: ResearchCapabilityId,
): ResearchWorkflowDraft => {
  const nextDraft = {
    ...draft,
    capabilities: { ...draft.capabilities },
    signalSources: { ...draft.signalSources },
    evaluation: { ...draft.evaluation },
  };

  if (capabilityId === "factor_catalog") {
    nextDraft.signalSources.factorCatalogVersion = "";
    nextDraft.signalSources.scoringFactorIdsInput = "";
  }

  if (capabilityId === "external_signals") {
    nextDraft.signalSources.externalSignalPolicyVersion = "";
  }

  if (capabilityId === "peer_context") {
    nextDraft.signalSources.clusterSnapshotVersion = "";
    nextDraft.signalSources.peerPolicyVersion = "";
  }

  if (capabilityId === "simulation_execution") {
    nextDraft.evaluation.executionRoute = "research_only";
    nextDraft.evaluation.simulationProfileId = "";
    nextDraft.evaluation.liveControlProfileId = "";
    nextDraft.evaluation.manualConfirmed = false;
    nextDraft.capabilities.adaptive_workflow = false;
    nextDraft.evaluation.adaptiveMode = "off";
    nextDraft.evaluation.adaptiveProfileId = "";
    nextDraft.evaluation.rewardDefinitionVersion = "";
    nextDraft.evaluation.stateDefinitionVersion = "";
    nextDraft.evaluation.rolloutControlVersion = "";
  }

  if (capabilityId === "adaptive_workflow") {
    nextDraft.evaluation.adaptiveMode = "off";
    nextDraft.evaluation.adaptiveProfileId = "";
    nextDraft.evaluation.rewardDefinitionVersion = "";
    nextDraft.evaluation.stateDefinitionVersion = "";
    nextDraft.evaluation.rolloutControlVersion = "";
  }

  return nextDraft;
};

export const withCapabilityToggled = (
  draft: ResearchWorkflowDraft,
  capabilityId: ResearchCapabilityId,
  isEnabled: boolean,
): ResearchWorkflowDraft => {
  const nextDraft: ResearchWorkflowDraft = {
    ...draft,
    capabilities: {
      ...draft.capabilities,
      [capabilityId]: isEnabled,
    },
    signalSources: { ...draft.signalSources },
    evaluation: { ...draft.evaluation },
  };

  if (!isEnabled) {
    if (capabilityId === "technical_indicators") {
      return draft;
    }
    return resetCapabilityFields(nextDraft, capabilityId);
  }

  if (capabilityId === "factor_catalog") {
    nextDraft.signalSources.factorCatalogVersion =
      nextDraft.signalSources.factorCatalogVersion || "factor_catalog_v1";
  }

  if (capabilityId === "external_signals") {
    nextDraft.signalSources.externalSignalPolicyVersion =
      nextDraft.signalSources.externalSignalPolicyVersion ||
      "tw_company_event_layer_v1";
  }

  if (capabilityId === "peer_context") {
    nextDraft.signalSources.clusterSnapshotVersion =
      nextDraft.signalSources.clusterSnapshotVersion ||
      "peer_cluster_kmeans_v1";
    nextDraft.signalSources.peerPolicyVersion =
      nextDraft.signalSources.peerPolicyVersion ||
      "cluster_nearest_neighbors_v1";
  }

  if (capabilityId === "simulation_execution") {
    nextDraft.evaluation.executionRoute =
      nextDraft.evaluation.executionRoute === "research_only"
        ? "simulation_internal_v1"
        : nextDraft.evaluation.executionRoute;
    nextDraft.evaluation.simulationProfileId =
      nextDraft.evaluation.simulationProfileId ||
      "simulation_internal_default_v1";
  }

  if (capabilityId === "adaptive_workflow") {
    nextDraft.capabilities.simulation_execution = true;
    nextDraft.evaluation.executionRoute =
      nextDraft.evaluation.executionRoute === "research_only"
        ? "simulation_internal_v1"
        : nextDraft.evaluation.executionRoute;
    nextDraft.evaluation.simulationProfileId =
      nextDraft.evaluation.simulationProfileId ||
      "simulation_internal_default_v1";
    nextDraft.evaluation.adaptiveMode =
      nextDraft.evaluation.adaptiveMode === "off"
        ? "shadow"
        : nextDraft.evaluation.adaptiveMode;
    nextDraft.evaluation.adaptiveProfileId =
      nextDraft.evaluation.adaptiveProfileId || "adaptive_shadow_v1";
    nextDraft.evaluation.rewardDefinitionVersion =
      nextDraft.evaluation.rewardDefinitionVersion ||
      "reward_daily_active_return_v1";
    nextDraft.evaluation.stateDefinitionVersion =
      nextDraft.evaluation.stateDefinitionVersion || "state_market_context_v1";
    nextDraft.evaluation.rolloutControlVersion =
      nextDraft.evaluation.rolloutControlVersion || "rollout_shadow_only_v1";
  }

  return nextDraft;
};

export const applyTemplateToDraft = (
  draft: ResearchWorkflowDraft,
  templateId: ResearchTemplateId,
): ResearchWorkflowDraft => {
  const seeded = createDefaultResearchWorkflowDraft(templateId);

  return {
    ...seeded,
    universe: {
      ...seeded.universe,
      market: draft.universe.market,
      symbolsInput: draft.universe.symbolsInput,
      startDate: draft.universe.startDate,
      endDate: draft.universe.endDate,
      returnTarget: draft.universe.returnTarget,
      horizonDays: draft.universe.horizonDays,
    },
  };
};

const getFallbackReadiness = (
  capabilityId: ResearchCapabilityId,
): CapabilityReadinessState => {
  const capability = getCapabilityDefinition(capabilityId);
  return {
    capabilityId,
    status: capability.status,
    summary: capability.summary,
    gateId: capability.gateRefs[0] ?? null,
    overallStatus: null,
  };
};

const upgradeStatus = (
  current: CapabilityReadinessState,
  incoming: CapabilityReadinessState,
) =>
  capabilityStatusRank[incoming.status] > capabilityStatusRank[current.status]
    ? incoming
    : current;

export const buildCapabilityReadinessMap = (
  gates: ResearchPhaseGateResponse[],
): Record<ResearchCapabilityId, CapabilityReadinessState> => {
  const readiness = Object.fromEntries(
    researchCapabilityRegistry.map((capability) => [
      capability.id,
      getFallbackReadiness(capability.id),
    ]),
  ) as Record<ResearchCapabilityId, CapabilityReadinessState>;

  return readiness;
};

export const updateModelFamily = (
  draft: ResearchWorkflowDraft,
  familyId: ModelFamilyId,
): ResearchWorkflowDraft => {
  const family = getModelFamilyById(familyId);
  const nextVariant =
    getAvailableVariantsForFamily(familyId)[0]?.id ?? family.variantIds[0];

  return {
    ...draft,
    modelFamily: {
      ...draft.modelFamily,
      familyId: family.id,
      variantId: nextVariant,
    },
  };
};

export const buildResearchRunPayloadFromWorkflow = (
  draft: ResearchWorkflowDraft,
): ResearchRunCreateRequest => ({
  runtime_mode: draft.modelFamily.runtimeMode,
  default_bundle_version:
    draft.modelFamily.runtimeMode === VNEXT_SPEC_MODE
      ? (draft.modelFamily.defaultBundleVersion ?? undefined)
      : undefined,
  market: "TW",
  symbols: parseSymbols(draft.universe.symbolsInput),
  date_range: {
    start: draft.universe.startDate,
    end: draft.universe.endDate,
  },
  return_target: draft.universe.returnTarget,
  horizon_days: draft.universe.horizonDays,
  features: draft.signalSources.indicatorRows.map((feature) => ({
    name: feature.name,
    window: feature.window,
    source: feature.source,
    shift: feature.shift,
  })),
  model: {
    type:
      draft.modelFamily.variantId === "lstm"
        ? "xgboost"
        : draft.modelFamily.variantId,
    params: {},
  },
  strategy: {
    type: "research_v1",
    threshold: draft.modelFamily.threshold ?? undefined,
    top_n: draft.modelFamily.topN ?? undefined,
    allow_proactive_sells: draft.modelFamily.allowProactiveSells,
  },
  execution: {
    slippage: draft.evaluation.slippage,
    fees: draft.evaluation.fees,
  },
  validation: draft.evaluation.enableValidation
    ? {
        method: draft.evaluation.validationMethod,
        splits: draft.evaluation.validationSplits,
        test_size: draft.evaluation.validationTestSize,
      }
    : undefined,
  baselines: draft.evaluation.baselines,
  portfolio_aum: draft.evaluation.portfolioAum ?? undefined,
  monitor_profile_id: draft.evaluation.recordAsMonitorRun
    ? DEFAULT_MONITOR_PROFILE_ID
    : undefined,
});

export const createWorkflowSubmissionSummary = (
  draft: ResearchWorkflowDraft,
): ResearchSubmissionSummary => ({
  templateId: draft.templateId,
  templateLabel: getTemplateById(draft.templateId).label,
  modelFamilyId: draft.modelFamily.familyId,
  modelFamilyLabel: getModelFamilyById(draft.modelFamily.familyId).label,
  modelVariantId: draft.modelFamily.variantId,
  modelVariantLabel: getModelVariantById(draft.modelFamily.variantId).label,
  capabilityIds: (
    Object.entries(draft.capabilities) as Array<[ResearchCapabilityId, boolean]>
  )
    .filter(([, isEnabled]) => isEnabled)
    .map(([capabilityId]) => capabilityId),
});

export const validateResearchWorkflow = (
  draft: ResearchWorkflowDraft,
  readiness: Record<ResearchCapabilityId, CapabilityReadinessState>,
): WorkflowValidationErrors => {
  const errors: WorkflowValidationErrors = {};
  const symbols = parseSymbols(draft.universe.symbolsInput);

  if (!symbols.length) {
    errors.symbolsInput = "Enter at least one symbol.";
  } else if (symbols.length !== new Set(symbols).size) {
    errors.symbolsInput = "Duplicate symbols are not allowed.";
  }

  if (!draft.universe.startDate || !draft.universe.endDate) {
    errors.dateRange = "Select both start and end dates.";
  } else if (draft.universe.startDate > draft.universe.endDate) {
    errors.dateRange = "End date must be on or after start date.";
  }

  if (draft.universe.horizonDays < 1) {
    errors.horizonDays = "Horizon must be at least 1 day.";
  }

  const uniqueFeatures = new Set<string>();
  for (const feature of draft.signalSources.indicatorRows) {
    const featureKey = `${feature.name}-${feature.window}-${feature.source}`;
    if (feature.window < 1 || feature.shift < 0) {
      errors[`feature-${feature.id}`] =
        "Window must be >= 1 and shift must be >= 0.";
      continue;
    }
    if (uniqueFeatures.has(featureKey)) {
      errors[`feature-${feature.id}`] =
        "Duplicate feature name/window/source combinations are not allowed.";
      continue;
    }
    uniqueFeatures.add(featureKey);
  }

  const selectedVariant = getModelVariantById(draft.modelFamily.variantId);
  const selectedFamily = getModelFamilyById(draft.modelFamily.familyId);
  if (
    selectedFamily.status !== "available" ||
    selectedVariant.status !== "available"
  ) {
    errors.modelVariant =
      "Choose an available model variant for this version of the product.";
  }

  if (draft.modelFamily.runtimeMode === VNEXT_SPEC_MODE) {
    if (!draft.modelFamily.defaultBundleVersion) {
      errors.runtime =
        "Default bundle is required when standard research mode is enabled.";
    }
  } else {
    if (draft.modelFamily.threshold === null) {
      errors.threshold = "Threshold is required in manual threshold mode.";
    }
    if (draft.modelFamily.topN === null) {
      errors.topN = "Top N is required in manual threshold mode.";
    }
  }

  if (draft.modelFamily.threshold !== null && draft.modelFamily.threshold < 0) {
    errors.threshold = "Threshold cannot be negative.";
  }

  if (draft.modelFamily.topN !== null && draft.modelFamily.topN < 1) {
    errors.topN = "Top N must be at least 1.";
  }

  if (draft.evaluation.slippage < 0 || draft.evaluation.fees < 0) {
    errors.execution = "Fees and slippage cannot be negative.";
  }

  if (
    draft.evaluation.portfolioAum !== null &&
    draft.evaluation.portfolioAum <= 0
  ) {
    errors.portfolioAum = "Portfolio AUM must be greater than 0.";
  }

  if (draft.evaluation.enableValidation) {
    if (draft.evaluation.validationSplits < 1) {
      errors.validationSplits = "Splits must be at least 1.";
    }
    if (
      draft.evaluation.validationTestSize <= 0 ||
      draft.evaluation.validationTestSize >= 1
    ) {
      errors.validationTestSize = "Test size must be between 0 and 1.";
    }
  }

  return errors;
};

export const deriveCapabilityIdsFromRun = (
  run: Partial<ResearchRunRecord & ResearchRunResponse>,
): ResearchCapabilityId[] => {
  void run;
  return ["technical_indicators"];
};

export const deriveSubmissionSummaryFromRun = (
  run: Partial<ResearchRunRecord & ResearchRunResponse>,
): ResearchSubmissionSummary => {
  const modelVariantId = (
    run.model_family === "gradient_boosted_trees"
      ? "xgboost"
      : run.model_family === "bagging_trees"
        ? "random_forest"
        : "xgboost"
  ) as ModelVariantId;

  return {
    templateId: "baseline_research",
    templateLabel: "Loaded Run",
    modelFamilyId: "tree_ensemble",
    modelFamilyLabel: "Tree Ensemble",
    modelVariantId,
    modelVariantLabel: getModelVariantById(modelVariantId).label,
    capabilityIds: deriveCapabilityIdsFromRun(run),
  };
};

export const summarizeBaselineComparison = (
  result: Partial<ResearchRunRecord & ResearchRunResponse> | null,
) => {
  if (!result?.metrics) {
    return null;
  }

  const baselineEntries = Object.entries(result.baselines ?? {}).filter(
    ([, metrics]) => typeof metrics.total_return === "number",
  );

  if (!baselineEntries.length) {
    return null;
  }

  const bestBaseline = baselineEntries.reduce((best, current) =>
    (current[1].total_return ?? Number.NEGATIVE_INFINITY) >
    (best[1].total_return ?? Number.NEGATIVE_INFINITY)
      ? current
      : best,
  );

  const delta =
    (result.metrics.total_return ?? 0) - (bestBaseline[1].total_return ?? 0);

  return {
    baselineName: bestBaseline[0],
    baselineReturn: bestBaseline[1].total_return ?? null,
    runReturn: result.metrics.total_return ?? null,
    delta,
    verdict: delta >= 0 ? "ahead" : "behind",
  };
};
