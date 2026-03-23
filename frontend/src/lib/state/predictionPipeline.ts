import type {
  BaselineName,
  DefaultBundleVersion,
  PredictionFeatureModuleId,
  PredictionFeatureModulePreset,
  PredictionPipelineDraft,
  ResearchFeatureRow,
  ResearchRunCreateRequest,
  RuntimeMode,
} from "../types";

export const DEFAULT_RUNTIME_MODE: RuntimeMode = "runtime_compatibility_mode";
export const VNEXT_SPEC_MODE: RuntimeMode = "vnext_spec_mode";
export const DEFAULT_BUNDLE_VERSION: DefaultBundleVersion = "research_spec_v1";
export const DEFAULT_THRESHOLD = 0.003;
export const DEFAULT_TOP_N = 5;
export const DEFAULT_MONITOR_PROFILE_ID = "p3_monitor_default_v1" as const;

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

export const predictionFeatureModulePresets: PredictionFeatureModulePreset[] = [
  {
    id: "technical_indicators",
    label: "Technical Indicators",
    description: "Use structured indicator rows as the core prediction inputs.",
    helper: "Supports MA and RSI in the current backend contract.",
  },
  {
    id: "factor_catalog",
    label: "Factor Catalog",
    description:
      "Attach scoring-ready factors from the factor catalog surface.",
    helper: "Best for event-derived or curated factor inputs.",
  },
  {
    id: "external_signals",
    label: "External Signals",
    description: "Attach policy-driven external signal lineage to the run.",
    helper: "Useful when company events or non-price signals matter.",
  },
  {
    id: "peer_context",
    label: "Peer Context",
    description: "Add clustering and peer overlays to the training frame.",
    helper: "Use when peer comparison context should inform the model.",
  },
];

export const createDefaultPredictionPipelineDraft =
  (): PredictionPipelineDraft => {
    const dateRange = createRecentDateRange();

    return {
      data: {
        market: "TW",
        symbolsInput: "2330",
        startDate: dateRange.start,
        endDate: dateRange.end,
        returnTarget: "open_to_open",
        horizonDays: 1,
      },
      feature: {
        selectedModuleIds: ["technical_indicators"],
        indicatorRows: [defaultIndicator(0, "ma"), defaultIndicator(1, "rsi")],
        factorCatalogVersion: "",
        scoringFactorIdsInput: "",
        externalSignalPolicyVersion: "tw_company_event_layer_v1",
        clusterSnapshotVersion: "",
        peerPolicyVersion: "",
      },
      model: {
        modelType: "xgboost",
        runtimeMode: DEFAULT_RUNTIME_MODE,
        defaultBundleVersion: null,
        threshold: DEFAULT_THRESHOLD,
        topN: DEFAULT_TOP_N,
        allowProactiveSells: true,
      },
      validation: {
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

const unique = <T>(values: T[]) => [...new Set(values)];

export const withFeatureModuleToggled = (
  draft: PredictionPipelineDraft,
  moduleId: PredictionFeatureModuleId,
  isEnabled: boolean,
): PredictionPipelineDraft => {
  const nextModuleIds = isEnabled
    ? unique([...draft.feature.selectedModuleIds, moduleId])
    : draft.feature.selectedModuleIds.filter((item) => item !== moduleId);

  const nextDraft: PredictionPipelineDraft = {
    ...draft,
    feature: {
      ...draft.feature,
      selectedModuleIds: nextModuleIds,
    },
  };

  if (
    moduleId === "technical_indicators" &&
    isEnabled &&
    !nextDraft.feature.indicatorRows.length
  ) {
    nextDraft.feature.indicatorRows = [
      defaultIndicator(0, "ma"),
      defaultIndicator(1, "rsi"),
    ];
  }

  if (!isEnabled) {
    if (moduleId === "factor_catalog") {
      nextDraft.feature.factorCatalogVersion = "";
      nextDraft.feature.scoringFactorIdsInput = "";
    }
    if (moduleId === "external_signals") {
      nextDraft.feature.externalSignalPolicyVersion = "";
    }
    if (moduleId === "peer_context") {
      nextDraft.feature.clusterSnapshotVersion = "";
      nextDraft.feature.peerPolicyVersion = "";
    }
  }

  if (isEnabled) {
    if (
      moduleId === "factor_catalog" &&
      !nextDraft.feature.factorCatalogVersion
    ) {
      nextDraft.feature.factorCatalogVersion = "factor_catalog_v1";
    }
    if (
      moduleId === "external_signals" &&
      !nextDraft.feature.externalSignalPolicyVersion
    ) {
      nextDraft.feature.externalSignalPolicyVersion =
        "tw_company_event_layer_v1";
    }
    if (moduleId === "peer_context") {
      if (!nextDraft.feature.clusterSnapshotVersion) {
        nextDraft.feature.clusterSnapshotVersion = "peer_cluster_kmeans_v1";
      }
      if (!nextDraft.feature.peerPolicyVersion) {
        nextDraft.feature.peerPolicyVersion = "cluster_nearest_neighbors_v1";
      }
    }
  }

  return nextDraft;
};

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

export const buildResearchRunPayloadFromPipeline = (
  draft: PredictionPipelineDraft,
): ResearchRunCreateRequest => ({
  runtime_mode: draft.model.runtimeMode,
  default_bundle_version:
    draft.model.runtimeMode === VNEXT_SPEC_MODE
      ? (draft.model.defaultBundleVersion ?? undefined)
      : undefined,
  market: draft.data.market,
  symbols: parseSymbols(draft.data.symbolsInput),
  date_range: {
    start: draft.data.startDate,
    end: draft.data.endDate,
  },
  return_target: draft.data.returnTarget,
  horizon_days: draft.data.horizonDays,
  features: draft.feature.indicatorRows.map((feature) => ({
    name: feature.name,
    window: feature.window,
    source: feature.source,
    shift: feature.shift,
  })),
  model: {
    type: draft.model.modelType,
    params: {},
  },
  strategy: {
    type: "research_v1",
    threshold: draft.model.threshold ?? undefined,
    top_n: draft.model.topN ?? undefined,
    allow_proactive_sells: draft.model.allowProactiveSells,
  },
  execution: {
    slippage: draft.validation.slippage,
    fees: draft.validation.fees,
  },
  validation: draft.validation.enableValidation
    ? {
        method: draft.validation.validationMethod,
        splits: draft.validation.validationSplits,
        test_size: draft.validation.validationTestSize,
      }
    : undefined,
  baselines: draft.validation.baselines,
  portfolio_aum: draft.validation.portfolioAum ?? undefined,
  monitor_profile_id: draft.validation.recordAsMonitorRun
    ? DEFAULT_MONITOR_PROFILE_ID
    : undefined,
  factor_catalog_version: draft.feature.selectedModuleIds.includes(
    "factor_catalog",
  )
    ? draft.feature.factorCatalogVersion || undefined
    : undefined,
  scoring_factor_ids: draft.feature.selectedModuleIds.includes("factor_catalog")
    ? parseScoringFactorIds(draft.feature.scoringFactorIdsInput)
    : undefined,
  external_signal_policy_version: draft.feature.selectedModuleIds.includes(
    "external_signals",
  )
    ? draft.feature.externalSignalPolicyVersion || undefined
    : undefined,
  cluster_snapshot_version: draft.feature.selectedModuleIds.includes(
    "peer_context",
  )
    ? draft.feature.clusterSnapshotVersion || undefined
    : undefined,
  peer_policy_version: draft.feature.selectedModuleIds.includes("peer_context")
    ? draft.feature.peerPolicyVersion || undefined
    : undefined,
  execution_route: draft.validation.executionRoute,
  simulation_profile_id: draft.validation.simulationProfileId || undefined,
  live_control_profile_id: draft.validation.liveControlProfileId || undefined,
  manual_confirmed: draft.validation.manualConfirmed,
  adaptive_mode: draft.validation.adaptiveMode,
  adaptive_profile_id: draft.validation.adaptiveProfileId || undefined,
  reward_definition_version:
    draft.validation.rewardDefinitionVersion || undefined,
  state_definition_version:
    draft.validation.stateDefinitionVersion || undefined,
  rollout_control_version: draft.validation.rolloutControlVersion || undefined,
});
