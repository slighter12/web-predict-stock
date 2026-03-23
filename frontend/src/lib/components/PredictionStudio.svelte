<script lang="ts">
    import { createMutation, createQuery } from "@tanstack/svelte-query";

    import {
        ApiError,
        createResearchRun,
        fetchResearchGate,
        fetchResearchRun,
        fetchSystemHealth,
    } from "../api";
    import {
        DEFAULT_BUNDLE_VERSION,
        DEFAULT_RUNTIME_MODE,
        VNEXT_SPEC_MODE,
        availableBaselines,
        buildResearchRunPayloadFromPipeline,
        createDefaultPredictionPipelineDraft,
        parseScoringFactorIds,
        parseSymbols,
        predictionFeatureModulePresets,
        withFeatureModuleToggled,
    } from "../state/predictionPipeline";
    import type {
        AppError,
        HealthResponse,
        PredictionFeatureModuleId,
        PredictionPipelineDraft,
        ResearchFeatureRow,
        ResearchPhaseGateResponse,
        ResearchRunRecord,
        ResearchRunResponse,
        RuntimeMode,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import EquityChart from "./EquityChart.svelte";
    import ResearchRunMetrics from "./research-runs/ResearchRunMetrics.svelte";
    import ResearchRunSignals from "./research-runs/ResearchRunSignals.svelte";
    import ResearchRunValidation from "./research-runs/ResearchRunValidation.svelte";

    type StageSummary = {
        id: StageId;
        label: string;
        title: string;
        summary: string;
    };

    type StageId =
        | "data"
        | "feature"
        | "model"
        | "validation"
        | "results";

    let draft: PredictionPipelineDraft = createDefaultPredictionPipelineDraft();
    let errors: Record<string, string> = {};
    let latestResult: ResearchRunResponse | null = null;
    let submitError: AppError | null = null;
    let researchRunRecord: ResearchRunRecord | null = null;
    let recordError: string | null = null;
    let runLookupId = "";
    let isRunLoading = false;
    let isAdvancedOpen = false;
    let activeStage: StageId = "data";

    const optionLabels: Record<string, string> = {
        research_only: "Research Only",
        simulation_internal_v1: "Internal Simulation",
        live_stub_v1: "Live Stub",
        runtime_compatibility_mode: "Manual Threshold Mode",
        vnext_spec_mode: "Standard Research Mode",
        open_to_open: "Open to Open",
        close_to_close: "Close to Close",
        open_to_close: "Open to Close",
        off: "Off",
        shadow: "Shadow",
        candidate: "Candidate",
        xgboost: "XGBoost",
        random_forest: "Random Forest",
        extra_trees: "Extra Trees",
    };

    const valueLabels: Record<string, string> = {
        runtime_compatibility_mode: "Manual Threshold Mode",
        vnext_spec_mode: "Standard Research Mode",
    };

    const gateNames: Record<string, string> = {
        P7: "External Data Readiness",
        P8: "Peer and Cluster Coverage",
        P9: "Simulation Setup",
        P10: "Live Control Setup",
        P11: "Adaptive Workflow Readiness",
    };

    const loadResearchRun = async (runId: string) => {
        if (!runId.trim()) {
            researchRunRecord = null;
            recordError = null;
            return;
        }

        isRunLoading = true;
        try {
            researchRunRecord = await fetchResearchRun(runId.trim());
            recordError = null;
            isAdvancedOpen = true;
        } catch (error) {
            researchRunRecord = null;
            if (error instanceof ApiError) {
                recordError = `${error.code}: ${error.message}`;
            } else {
                recordError = "Unable to load saved run details.";
            }
        } finally {
            isRunLoading = false;
        }
    };

    const healthQuery = createQuery(() => ({
        queryKey: ["system", "health"],
        queryFn: fetchSystemHealth,
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const p7GateQuery = createQuery(() => ({
        queryKey: ["research", "gate", "p7"],
        queryFn: () => fetchResearchGate("p7"),
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const p8GateQuery = createQuery(() => ({
        queryKey: ["research", "gate", "p8"],
        queryFn: () => fetchResearchGate("p8"),
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const p9GateQuery = createQuery(() => ({
        queryKey: ["research", "gate", "p9"],
        queryFn: () => fetchResearchGate("p9"),
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const p10GateQuery = createQuery(() => ({
        queryKey: ["research", "gate", "p10"],
        queryFn: () => fetchResearchGate("p10"),
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const p11GateQuery = createQuery(() => ({
        queryKey: ["research", "gate", "p11"],
        queryFn: () => fetchResearchGate("p11"),
        retry: false,
        refetchOnWindowFocus: false,
    }));

    const researchRunMutation = createMutation(() => ({
        mutationFn: createResearchRun,
        onSuccess: (data) => {
            latestResult = data;
            submitError = null;
            runLookupId = data.run_id;
            isAdvancedOpen = true;
            activeStage = "results";
            void loadResearchRun(data.run_id);
        },
        onError: (error) => {
            latestResult = null;
            if (error instanceof ApiError) {
                submitError = error;
                return;
            }

            submitError = {
                status: 0,
                code: "NETWORK_ERROR",
                message:
                    "Unable to reach the backend. Check VITE_API_BASE_URL and backend status.",
                requestId: null,
            };
        },
    }));

    const hasModule = (moduleId: PredictionFeatureModuleId) =>
        draft.feature.selectedModuleIds.includes(moduleId);

    const getOptionLabel = (value: string) => optionLabels[value] ?? value;
    const runtimeUsesDefaults = () =>
        draft.model.runtimeMode === VNEXT_SPEC_MODE;
    const serialize = (value: unknown) => JSON.stringify(value, null, 2);
    const toLabel = (value: string) =>
        value
            .replace(/^GATE-/, "")
            .replace(/^KPI-/, "")
            .replace(/[_-]+/g, " ")
            .toLowerCase()
            .replace(/\b\w/g, (character) => character.toUpperCase());
    const formatDisplayValue = (value: string | null | undefined) =>
        value === null || value === undefined
            ? "N/A"
            : (valueLabels[value] ?? toLabel(value));
    const formatRatio = (value: number | null | undefined) =>
        value === null || value === undefined
            ? "N/A"
            : `${(value * 100).toFixed(1)}%`;
    const getGateTitle = (gateId: string) =>
        Object.entries(gateNames).find(([phase]) =>
            gateId.includes(phase),
        )?.[1] ?? "Readiness Check";
    const summarizeGate = (gate: ResearchPhaseGateResponse) => {
        const metricValues = Object.values(gate.metrics);
        const artifactValues = Object.values(gate.artifacts);

        return {
            passedMetrics: metricValues.filter(
                (metric) => metric.status === "pass",
            ).length,
            totalMetrics: metricValues.length,
            passedArtifacts: artifactValues.filter(
                (artifact) => artifact.status === "pass",
            ).length,
            totalArtifacts: artifactValues.length,
        };
    };

    const addIndicator = () => {
        draft = {
            ...draft,
            feature: {
                ...draft.feature,
                indicatorRows: [
                    ...draft.feature.indicatorRows,
                    {
                        id: `feature-${Date.now()}`,
                        name: "ma",
                        window: 5,
                        source: "close",
                        shift: 1,
                    },
                ],
            },
        };
    };

    const removeIndicator = (id: string) => {
        if (draft.feature.indicatorRows.length === 1) {
            return;
        }

        draft = {
            ...draft,
            feature: {
                ...draft.feature,
                indicatorRows: draft.feature.indicatorRows.filter(
                    (feature) => feature.id !== id,
                ),
            },
        };
    };

    const updateIndicator = <K extends keyof ResearchFeatureRow>(
        id: string,
        key: K,
        value: ResearchFeatureRow[K],
    ) => {
        draft = {
            ...draft,
            feature: {
                ...draft.feature,
                indicatorRows: draft.feature.indicatorRows.map((feature) =>
                    feature.id === id ? { ...feature, [key]: value } : feature,
                ),
            },
        };
    };

    const toggleBaseline = (baseline: (typeof availableBaselines)[number]) => {
        const baselines = draft.validation.baselines.includes(baseline)
            ? draft.validation.baselines.filter((item) => item !== baseline)
            : [...draft.validation.baselines, baseline];

        draft = {
            ...draft,
            validation: {
                ...draft.validation,
                baselines,
            },
        };
    };

    const toggleModule = (moduleId: PredictionFeatureModuleId) => {
        draft = withFeatureModuleToggled(draft, moduleId, !hasModule(moduleId));
    };

    const handleRuntimeModeChange = (value: RuntimeMode) => {
        const previousMode = draft.model.runtimeMode;
        draft = {
            ...draft,
            model: {
                ...draft.model,
                runtimeMode: value,
                defaultBundleVersion:
                    value === VNEXT_SPEC_MODE
                        ? (draft.model.defaultBundleVersion ??
                          DEFAULT_BUNDLE_VERSION)
                        : null,
                threshold:
                    previousMode === VNEXT_SPEC_MODE &&
                    value === DEFAULT_RUNTIME_MODE
                        ? (draft.model.threshold ?? 0.003)
                        : draft.model.threshold,
                topN:
                    previousMode === VNEXT_SPEC_MODE &&
                    value === DEFAULT_RUNTIME_MODE
                        ? (draft.model.topN ?? 5)
                        : draft.model.topN,
            },
        };
    };

    const stageOrder: StageId[] = [
        "data",
        "feature",
        "model",
        "validation",
        "results",
    ];

    const moveStage = (direction: -1 | 1) => {
        const currentIndex = stageOrder.indexOf(activeStage);
        const nextIndex = currentIndex + direction;
        if (nextIndex < 0 || nextIndex >= stageOrder.length) {
            return;
        }
        activeStage = stageOrder[nextIndex];
    };

    const canMoveToResults = () => latestResult !== null;

    const validate = () => {
        const nextErrors: Record<string, string> = {};
        const symbols = parseSymbols(draft.data.symbolsInput);

        if (!symbols.length) {
            nextErrors.symbolsInput = "Enter at least one symbol.";
        } else if (symbols.length !== new Set(symbols).size) {
            nextErrors.symbolsInput = "Duplicate symbols are not allowed.";
        }

        if (!draft.data.startDate || !draft.data.endDate) {
            nextErrors.dateRange = "Select both start and end dates.";
        } else if (draft.data.startDate > draft.data.endDate) {
            nextErrors.dateRange = "End date must be on or after start date.";
        }

        if (draft.data.horizonDays < 1) {
            nextErrors.horizonDays = "Horizon must be at least 1 day.";
        }

        if (hasModule("technical_indicators")) {
            const uniqueFeatures = new Set<string>();
            draft.feature.indicatorRows.forEach((feature) => {
                const featureKey = `${feature.name}-${feature.window}-${feature.source}`;
                if (feature.window < 1 || feature.shift < 0) {
                    nextErrors[`feature-${feature.id}`] =
                        "Window must be >= 1 and shift must be >= 0.";
                } else if (uniqueFeatures.has(featureKey)) {
                    nextErrors[`feature-${feature.id}`] =
                        "Duplicate feature name/window/source combinations are not allowed.";
                } else {
                    uniqueFeatures.add(featureKey);
                }
            });
        }

        if (!draft.feature.selectedModuleIds.length) {
            nextErrors.featureModules = "Select at least one feature module.";
        }

        if (hasModule("factor_catalog")) {
            if (!draft.feature.factorCatalogVersion.trim()) {
                nextErrors.factorCatalogVersion =
                    "Factor catalog version is required when the factor module is enabled.";
            }
            const scoringFactorIds = parseScoringFactorIds(
                draft.feature.scoringFactorIdsInput,
            );
            if (scoringFactorIds.length !== new Set(scoringFactorIds).size) {
                nextErrors.scoringFactorIdsInput =
                    "Scoring factor IDs must be unique.";
            }
        }

        if (
            hasModule("external_signals") &&
            !draft.feature.externalSignalPolicyVersion.trim()
        ) {
            nextErrors.externalSignalPolicyVersion =
                "External signal policy is required when the signal module is enabled.";
        }

        if (hasModule("peer_context")) {
            if (!draft.feature.clusterSnapshotVersion.trim()) {
                nextErrors.clusterSnapshotVersion =
                    "Cluster snapshot version is required when peer context is enabled.";
            }
            if (!draft.feature.peerPolicyVersion.trim()) {
                nextErrors.peerPolicyVersion =
                    "Peer policy version is required when peer context is enabled.";
            }
        }

        if (runtimeUsesDefaults()) {
            if (!draft.model.defaultBundleVersion) {
                nextErrors.runtime =
                    "Default bundle is required in standard research mode.";
            }
            if (draft.model.threshold !== null && draft.model.threshold < 0) {
                nextErrors.threshold = "Threshold cannot be negative.";
            }
            if (draft.model.topN !== null && draft.model.topN < 1) {
                nextErrors.topN = "Top N must be at least 1.";
            }
        } else {
            if (draft.model.threshold === null) {
                nextErrors.threshold =
                    "Threshold is required in manual threshold mode.";
            } else if (draft.model.threshold < 0) {
                nextErrors.threshold = "Threshold cannot be negative.";
            }
            if (draft.model.topN === null) {
                nextErrors.topN = "Top N is required in manual threshold mode.";
            } else if (draft.model.topN < 1) {
                nextErrors.topN = "Top N must be at least 1.";
            }
        }

        if (draft.validation.slippage < 0 || draft.validation.fees < 0) {
            nextErrors.execution = "Fees and slippage cannot be negative.";
        }

        if (
            draft.validation.portfolioAum !== null &&
            draft.validation.portfolioAum <= 0
        ) {
            nextErrors.portfolioAum = "Portfolio AUM must be greater than 0.";
        }

        if (draft.validation.enableValidation) {
            if (draft.validation.validationSplits < 1) {
                nextErrors.validationSplits = "Splits must be at least 1.";
            }
            if (
                draft.validation.validationTestSize <= 0 ||
                draft.validation.validationTestSize >= 1
            ) {
                nextErrors.validationTestSize =
                    "Test size must be between 0 and 1.";
            }
        }

        if (draft.validation.adaptiveMode !== "off") {
            if (
                !draft.validation.adaptiveProfileId ||
                !draft.validation.rewardDefinitionVersion ||
                !draft.validation.stateDefinitionVersion ||
                !draft.validation.rolloutControlVersion
            ) {
                nextErrors.adaptiveMode =
                    "Adaptive runs require profile, reward, state, and rollout control versions.";
            }
        }

        errors = nextErrors;
        return Object.keys(nextErrors).length === 0;
    };

    const resetPipeline = () => {
        draft = createDefaultPredictionPipelineDraft();
        latestResult = null;
        submitError = null;
        errors = {};
        activeStage = "data";
    };

    const submitPipeline = () => {
        if (!validate()) {
            return;
        }

        submitError = null;
        researchRunMutation.mutate(buildResearchRunPayloadFromPipeline(draft));
    };

    const submitLookup = () => {
        void loadResearchRun(runLookupId);
    };

    $: stageSummaries = [
        {
            id: "data",
            label: "01",
            title: "Data",
            summary: `${draft.data.market} / ${parseSymbols(draft.data.symbolsInput).length || 0} symbol(s) / ${draft.data.returnTarget}`,
        },
        {
            id: "feature",
            label: "02",
            title: "Feature",
            summary:
                draft.feature.selectedModuleIds.length > 0
                    ? draft.feature.selectedModuleIds
                          .map(
                              (moduleId) =>
                                  predictionFeatureModulePresets.find(
                                      (preset) => preset.id === moduleId,
                                  )?.label,
                          )
                          .filter(Boolean)
                          .join(" + ")
                    : "Select feature modules",
        },
        {
            id: "model",
            label: "03",
            title: "Model",
            summary: `${getOptionLabel(draft.model.modelType)} / ${getOptionLabel(draft.model.runtimeMode)}`,
        },
        {
            id: "validation",
            label: "04",
            title: "Validation",
            summary: draft.validation.enableValidation
                ? `${draft.validation.validationMethod} / ${draft.validation.baselines.length} baselines`
                : `${getOptionLabel(draft.validation.executionRoute)} / validation off`,
        },
        {
            id: "results",
            label: "05",
            title: "Results",
            summary: latestResult
                ? `Run ${latestResult.run_id} is ready for review`
                : "Submit the workflow to populate results",
        },
    ] as StageSummary[];

    $: activeStageSummary =
        stageSummaries.find((stage) => stage.id === activeStage) ??
        stageSummaries[0];

    $: healthState = {
        health: healthQuery.data ?? null,
        isHealthLoading: healthQuery.isPending,
        healthError:
            healthQuery.error instanceof Error
                ? healthQuery.error.message
                : null,
    } as {
        health: HealthResponse | null;
        isHealthLoading: boolean;
        healthError: string | null;
    };

    $: gateState = {
        gates: [
            p7GateQuery.data,
            p8GateQuery.data,
            p9GateQuery.data,
            p10GateQuery.data,
            p11GateQuery.data,
        ].filter(Boolean) as ResearchPhaseGateResponse[],
        gateError:
            [
                p7GateQuery.error,
                p8GateQuery.error,
                p9GateQuery.error,
                p10GateQuery.error,
                p11GateQuery.error,
            ].find((item) => item instanceof Error) instanceof Error
                ? (
                      [
                          p7GateQuery.error,
                          p8GateQuery.error,
                          p9GateQuery.error,
                          p10GateQuery.error,
                          p11GateQuery.error,
                      ].find((item) => item instanceof Error) as Error
                  ).message
                : null,
    } as {
        gates: ResearchPhaseGateResponse[];
        gateError: string | null;
    };
</script>

<WorkspaceSection
    id="prediction-studio"
    eyebrow="Prediction Studio"
    title="Build the prediction flow before you inspect the run internals."
    description="Select feature modules, choose the modeling stack, and validate the workflow in one continuous surface. Maintenance stays available for data repair, not as the primary entry point."
>
    <svelte:fragment slot="actions">
        <a class="ghost-link" href="#maintenance-workspace">Open Maintenance</a>
    </svelte:fragment>

    <div class="studio-shell">
        <div class="surface surface--lead">
            <div class="surface-header surface-header--lead">
                <div>
                    <p class="eyebrow">Prediction Flow</p>
                    <h3>Work through one stage at a time.</h3>
                </div>
                <div class="lead-summary">
                    <strong
                        >{activeStageSummary.label} {activeStageSummary.title}</strong
                    >
                    <p>{activeStageSummary.summary}</p>
                </div>
            </div>
            <div class="stage-strip" role="tablist" aria-label="Prediction flow stages">
                {#each stageSummaries as stage}
                    <button
                        type="button"
                        class:stage-pill={true}
                        class:stage-pill--active={stage.id === activeStage}
                        disabled={stage.id === "results" && !canMoveToResults()}
                        onclick={() => (activeStage = stage.id)}
                    >
                        <span>{stage.label}</span>
                        <strong>{stage.title}</strong>
                    </button>
                {/each}
            </div>
            <p class="surface-note">
                Routine data loading should stay in CLI/scripts. Use
                <a href="#maintenance-workspace">Maintenance</a>
                only when repair or replay is needed.
            </p>
        </div>

        {#if submitError}
            <div class="error-banner" role="alert">
                <strong>{submitError.code}</strong>
                <span>{submitError.message}</span>
                {#if submitError.runId}<span>run ID: {submitError.runId}</span
                    >{/if}
                {#if submitError.requestId}
                    <span>request ID: {submitError.requestId}</span>
                {/if}
            </div>
        {/if}

        {#if researchRunMutation.isPending}
            <div class="status-banner" aria-live="polite">
                <strong>Prediction workflow in progress</strong>
                <span>
                    The previous result stays visible while the backend compiles
                    the next run.
                </span>
            </div>
        {/if}

        {#if activeStage === "data"}
            <div class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">01 Data</p>
                        <h3>Choose the market context</h3>
                    </div>
                    <button
                        type="button"
                        class="secondary"
                        onclick={resetPipeline}>Reset</button
                    >
                </div>
                <div class="group four">
                    <label>
                        <span>Market</span>
                        <select bind:value={draft.data.market}>
                            <option value="TW">TW</option>
                            <option value="US">US</option>
                        </select>
                    </label>
                    <label class="wide">
                        <span>Symbols</span>
                        <input
                            bind:value={draft.data.symbolsInput}
                            placeholder="2330, 2317, AAPL"
                        />
                        {#if errors.symbolsInput}<small>{errors.symbolsInput}</small
                            >{/if}
                    </label>
                    <label>
                        <span>Start Date</span>
                        <input type="date" bind:value={draft.data.startDate} />
                    </label>
                    <label>
                        <span>End Date</span>
                        <input type="date" bind:value={draft.data.endDate} />
                    </label>
                    <label>
                        <span>Return Target</span>
                        <select bind:value={draft.data.returnTarget}>
                            <option value="open_to_open"
                                >{getOptionLabel("open_to_open")}</option
                            >
                            <option value="close_to_close"
                                >{getOptionLabel("close_to_close")}</option
                            >
                            <option value="open_to_close"
                                >{getOptionLabel("open_to_close")}</option
                            >
                        </select>
                    </label>
                    <label>
                        <span>Horizon Days</span>
                        <input
                            type="number"
                            min="1"
                            bind:value={draft.data.horizonDays}
                        />
                        {#if errors.horizonDays}<small>{errors.horizonDays}</small
                            >{/if}
                    </label>
                </div>
                {#if errors.dateRange}<small>{errors.dateRange}</small>{/if}
                <div class="info-card">
                    <strong>Data readiness</strong>
                    <p>
                        If daily data is stale, a replay fails, or a symbol
                        needs manual repair, jump to <a
                            href="#maintenance-workspace">Maintenance</a
                        >. The prediction flow itself stays focused on modeling.
                    </p>
                </div>
                <div class="stage-actions">
                    <button
                        type="button"
                        class="submit"
                        onclick={() => (activeStage = "feature")}
                    >
                        Continue to Feature
                    </button>
                </div>
            </div>
        {/if}

        {#if activeStage === "feature"}
            <div class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">02 Feature</p>
                        <h3>Select the feature modules</h3>
                    </div>
                    <span class="muted"
                        >{draft.feature.selectedModuleIds.length} module(s)</span
                    >
                </div>

                <div class="module-grid">
                    {#each predictionFeatureModulePresets as preset}
                        <button
                            type="button"
                            class:module-card={true}
                            class:module-card--active={hasModule(preset.id)}
                            onclick={() => toggleModule(preset.id)}
                        >
                            <span>{preset.label}</span>
                            <strong>{preset.description}</strong>
                            <p>{preset.helper}</p>
                        </button>
                    {/each}
                </div>
                {#if errors.featureModules}<small>{errors.featureModules}</small
                    >{/if}

                {#if hasModule("technical_indicators")}
                    <div class="module-section">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Core Inputs</p>
                                <h4>Technical indicator rows</h4>
                            </div>
                            <button
                                type="button"
                                class="secondary"
                                onclick={addIndicator}>Add Indicator</button
                            >
                        </div>
                        <div class="feature-list">
                            {#each draft.feature.indicatorRows as feature}
                                <div class="feature-row">
                                    <label>
                                        <span>Name</span>
                                        <select
                                            value={feature.name}
                                            onchange={(event) =>
                                                updateIndicator(
                                                    feature.id,
                                                    "name",
                                                    (
                                                        event.currentTarget as HTMLSelectElement
                                                    )
                                                        .value as ResearchFeatureRow["name"],
                                                )}
                                        >
                                            <option value="ma">ma</option>
                                            <option value="rsi">rsi</option>
                                        </select>
                                    </label>
                                    <label>
                                        <span>Window</span>
                                        <input
                                            type="number"
                                            min="1"
                                            value={feature.window}
                                            onchange={(event) =>
                                                updateIndicator(
                                                    feature.id,
                                                    "window",
                                                    Number(
                                                        (
                                                            event.currentTarget as HTMLInputElement
                                                        ).value,
                                                    ),
                                                )}
                                        />
                                    </label>
                                    <label>
                                        <span>Source</span>
                                        <select
                                            value={feature.source}
                                            onchange={(event) =>
                                                updateIndicator(
                                                    feature.id,
                                                    "source",
                                                    (
                                                        event.currentTarget as HTMLSelectElement
                                                    )
                                                        .value as ResearchFeatureRow["source"],
                                                )}
                                        >
                                            <option value="open">open</option>
                                            <option value="high">high</option>
                                            <option value="low">low</option>
                                            <option value="close">close</option>
                                            <option value="volume">volume</option>
                                        </select>
                                    </label>
                                    <label>
                                        <span>Shift</span>
                                        <input
                                            type="number"
                                            min="0"
                                            value={feature.shift}
                                            onchange={(event) =>
                                                updateIndicator(
                                                    feature.id,
                                                    "shift",
                                                    Number(
                                                        (
                                                            event.currentTarget as HTMLInputElement
                                                        ).value,
                                                    ),
                                                )}
                                        />
                                    </label>
                                    <button
                                        type="button"
                                        class="danger"
                                        onclick={() => removeIndicator(feature.id)}
                                    >
                                        Remove
                                    </button>
                                    {#if errors[`feature-${feature.id}`]}
                                        <small class="full"
                                            >{errors[`feature-${feature.id}`]}</small
                                        >
                                    {/if}
                                </div>
                            {/each}
                        </div>
                    </div>
                {/if}

                {#if hasModule("factor_catalog")}
                    <div class="group two module-fields">
                        <label>
                            <span>Factor Catalog Version</span>
                            <input
                                bind:value={draft.feature.factorCatalogVersion}
                                placeholder="factor_catalog_v1"
                            />
                            {#if errors.factorCatalogVersion}<small
                                    >{errors.factorCatalogVersion}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Scoring Factor IDs</span>
                            <input
                                bind:value={draft.feature.scoringFactorIdsInput}
                                placeholder="company_listing_age_days_v1, important_event_count_30d_v1"
                            />
                            {#if errors.scoringFactorIdsInput}<small
                                    >{errors.scoringFactorIdsInput}</small
                                >{/if}
                        </label>
                    </div>
                {/if}

                {#if hasModule("external_signals")}
                    <div class="group one module-fields">
                        <label>
                            <span>External Signal Policy</span>
                            <input
                                bind:value={
                                    draft.feature.externalSignalPolicyVersion
                                }
                            />
                            {#if errors.externalSignalPolicyVersion}<small
                                    >{errors.externalSignalPolicyVersion}</small
                                >{/if}
                        </label>
                    </div>
                {/if}

                {#if hasModule("peer_context")}
                    <div class="group two module-fields">
                        <label>
                            <span>Cluster Snapshot Version</span>
                            <input
                                bind:value={draft.feature.clusterSnapshotVersion}
                                placeholder="peer_cluster_kmeans_v1"
                            />
                            {#if errors.clusterSnapshotVersion}<small
                                    >{errors.clusterSnapshotVersion}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Peer Policy Version</span>
                            <input
                                bind:value={draft.feature.peerPolicyVersion}
                                placeholder="cluster_nearest_neighbors_v1"
                            />
                            {#if errors.peerPolicyVersion}<small
                                    >{errors.peerPolicyVersion}</small
                                >{/if}
                        </label>
                    </div>
                {/if}

                <div class="stage-actions">
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => moveStage(-1)}
                    >
                        Back
                    </button>
                    <button
                        type="button"
                        class="submit"
                        onclick={() => (activeStage = "model")}
                    >
                        Continue to Model
                    </button>
                </div>
            </div>
        {/if}

        {#if activeStage === "model"}
            <div class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">03 Model</p>
                        <h3>Choose the modeling stack</h3>
                    </div>
                    <span class="muted"
                        >Compiled into the existing research request</span
                    >
                </div>
                <div class="group four">
                    <label>
                        <span>Model Type</span>
                        <select bind:value={draft.model.modelType}>
                            <option value="xgboost"
                                >{getOptionLabel("xgboost")}</option
                            >
                            <option value="random_forest"
                                >{getOptionLabel("random_forest")}</option
                            >
                            <option value="extra_trees"
                                >{getOptionLabel("extra_trees")}</option
                            >
                        </select>
                    </label>
                    <label>
                        <span>Selection Mode</span>
                        <select
                            value={draft.model.runtimeMode}
                            onchange={(event) =>
                                handleRuntimeModeChange(
                                    (event.currentTarget as HTMLSelectElement)
                                        .value as RuntimeMode,
                                )}
                        >
                            <option value={DEFAULT_RUNTIME_MODE}
                                >{getOptionLabel(DEFAULT_RUNTIME_MODE)}</option
                            >
                            <option value={VNEXT_SPEC_MODE}
                                >{getOptionLabel(VNEXT_SPEC_MODE)}</option
                            >
                        </select>
                        {#if errors.runtime}<small>{errors.runtime}</small>{/if}
                    </label>
                    <label>
                        <span>Default Bundle</span>
                        <select
                            value={draft.model.defaultBundleVersion ?? ""}
                            disabled={!runtimeUsesDefaults()}
                            onchange={(event) =>
                                (draft = {
                                    ...draft,
                                    model: {
                                        ...draft.model,
                                        defaultBundleVersion: ((
                                            event.currentTarget as HTMLSelectElement
                                        ).value ||
                                            null) as typeof draft.model.defaultBundleVersion,
                                    },
                                })}
                        >
                            <option value="">None</option>
                            <option value={DEFAULT_BUNDLE_VERSION}
                                >Default Research Spec</option
                            >
                        </select>
                    </label>
                    <label class="toggle">
                        <span>Allow Proactive Sells</span>
                        <input
                            type="checkbox"
                            bind:checked={draft.model.allowProactiveSells}
                        />
                    </label>
                </div>
                <div class="group three">
                    <label>
                        <span>Threshold</span>
                        <input
                            type="number"
                            step="0.001"
                            bind:value={draft.model.threshold}
                        />
                        {#if errors.threshold}<small>{errors.threshold}</small>{/if}
                    </label>
                    <label>
                        <span>Top N</span>
                        <input
                            type="number"
                            min="1"
                            bind:value={draft.model.topN}
                        />
                        {#if errors.topN}<small>{errors.topN}</small>{/if}
                    </label>
                    <div class="summary-chip">
                        <strong>Current mix</strong>
                        <span>
                            {getOptionLabel(draft.model.modelType)} with
                            {draft.feature.selectedModuleIds.length} feature module(s)
                        </span>
                    </div>
                </div>
                <div class="stage-actions">
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => moveStage(-1)}
                    >
                        Back
                    </button>
                    <button
                        type="button"
                        class="submit"
                        onclick={() => (activeStage = "validation")}
                    >
                        Continue to Validation
                    </button>
                </div>
            </div>
        {/if}

        {#if activeStage === "validation"}
            <div class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">04 Validation</p>
                        <h3>Configure validation and execution posture</h3>
                    </div>
                </div>
                <div class="group three">
                    <label class="toggle">
                        <span>Validation Enabled</span>
                        <input
                            type="checkbox"
                            bind:checked={draft.validation.enableValidation}
                        />
                    </label>
                    <label>
                        <span>Execution Mode</span>
                        <select bind:value={draft.validation.executionRoute}>
                            <option value="research_only"
                                >{getOptionLabel("research_only")}</option
                            >
                            <option value="simulation_internal_v1"
                                >{getOptionLabel("simulation_internal_v1")}</option
                            >
                            <option value="live_stub_v1"
                                >{getOptionLabel("live_stub_v1")}</option
                            >
                        </select>
                    </label>
                    <label>
                        <span>Baselines</span>
                        <div class="baseline-list">
                            {#each availableBaselines as baseline}
                                <label class="checkbox">
                                    <input
                                        type="checkbox"
                                        checked={draft.validation.baselines.includes(
                                            baseline,
                                        )}
                                        onchange={() => toggleBaseline(baseline)}
                                    />
                                    <span>{baseline}</span>
                                </label>
                            {/each}
                        </div>
                    </label>
                </div>
                {#if draft.validation.enableValidation}
                    <div class="group three">
                        <label>
                            <span>Validation Method</span>
                            <select bind:value={draft.validation.validationMethod}>
                                <option value="holdout">holdout</option>
                                <option value="walk_forward">walk_forward</option>
                                <option value="rolling_window"
                                    >rolling_window</option
                                >
                                <option value="expanding_window"
                                    >expanding_window</option
                                >
                            </select>
                        </label>
                        <label>
                            <span>Splits</span>
                            <input
                                type="number"
                                min="1"
                                bind:value={draft.validation.validationSplits}
                            />
                            {#if errors.validationSplits}<small
                                    >{errors.validationSplits}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Test Size</span>
                            <input
                                type="number"
                                min="0.01"
                                max="0.99"
                                step="0.01"
                                bind:value={draft.validation.validationTestSize}
                            />
                            {#if errors.validationTestSize}<small
                                    >{errors.validationTestSize}</small
                                >{/if}
                        </label>
                    </div>
                {/if}

                <details class="advanced-config">
                    <summary>Advanced execution and monitoring</summary>
                    <div class="group four advanced-grid">
                        <label>
                            <span>Slippage</span>
                            <input
                                type="number"
                                min="0"
                                step="0.001"
                                bind:value={draft.validation.slippage}
                            />
                        </label>
                        <label>
                            <span>Fees</span>
                            <input
                                type="number"
                                min="0"
                                step="0.001"
                                bind:value={draft.validation.fees}
                            />
                        </label>
                        <label>
                            <span>Portfolio AUM</span>
                            <input
                                type="number"
                                min="0"
                                step="100000"
                                bind:value={draft.validation.portfolioAum}
                                placeholder="Optional"
                            />
                            {#if errors.portfolioAum}<small
                                    >{errors.portfolioAum}</small
                                >{/if}
                        </label>
                        <label class="toggle">
                            <span>Save as monitoring run</span>
                            <input
                                type="checkbox"
                                bind:checked={draft.validation.recordAsMonitorRun}
                            />
                        </label>
                        <label>
                            <span>Simulation Profile</span>
                            <input
                                bind:value={draft.validation.simulationProfileId}
                                placeholder="simulation_internal_default_v1"
                            />
                        </label>
                        <label>
                            <span>Live Control Profile</span>
                            <input
                                bind:value={draft.validation.liveControlProfileId}
                                placeholder="live_stub_default_v1"
                            />
                        </label>
                        <label class="toggle">
                            <span>Manual Approval Confirmed</span>
                            <input
                                type="checkbox"
                                bind:checked={draft.validation.manualConfirmed}
                            />
                        </label>
                        <label>
                            <span>Adaptive Mode</span>
                            <select bind:value={draft.validation.adaptiveMode}>
                                <option value="off">{getOptionLabel("off")}</option>
                                <option value="shadow"
                                    >{getOptionLabel("shadow")}</option
                                >
                                <option value="candidate"
                                    >{getOptionLabel("candidate")}</option
                                >
                            </select>
                            {#if errors.adaptiveMode}<small
                                    >{errors.adaptiveMode}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Adaptive Profile</span>
                            <input
                                bind:value={draft.validation.adaptiveProfileId}
                                placeholder="adaptive_shadow_v1"
                            />
                        </label>
                        <label>
                            <span>Reward Version</span>
                            <input
                                bind:value={
                                    draft.validation.rewardDefinitionVersion
                                }
                                placeholder="reward_daily_active_return_v1"
                            />
                        </label>
                        <label>
                            <span>State Version</span>
                            <input
                                bind:value={draft.validation.stateDefinitionVersion}
                                placeholder="state_market_context_v1"
                            />
                        </label>
                        <label>
                            <span>Rollout Control</span>
                            <input
                                bind:value={draft.validation.rolloutControlVersion}
                                placeholder="rollout_shadow_only_v1"
                            />
                        </label>
                    </div>
                    {#if errors.execution}<small>{errors.execution}</small>{/if}
                </details>

                <div class="submit-row">
                    <button
                        type="button"
                        class="submit"
                        onclick={submitPipeline}
                        disabled={researchRunMutation.isPending}
                    >
                        {researchRunMutation.isPending
                            ? "Compiling Prediction Workflow..."
                            : "Run Prediction Workflow"}
                    </button>
                    <p class="muted">
                        The UI stages compile into the current backend run contract.
                    </p>
                </div>
                <div class="stage-actions">
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => moveStage(-1)}
                    >
                        Back
                    </button>
                    {#if latestResult}
                        <button
                            type="button"
                            class="secondary"
                            onclick={() => (activeStage = "results")}
                        >
                            Open Latest Result
                        </button>
                    {/if}
                </div>
            </div>
        {/if}

        {#if activeStage === "results"}
            <div class="surface surface--results">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">05 Results</p>
                        <h3>Review outcomes in the same flow</h3>
                    </div>
                    {#if latestResult}<span class="run-id"
                            >{latestResult.run_id}</span
                        >{/if}
                </div>

                {#if latestResult}
                    <ResearchRunMetrics metrics={latestResult.metrics} />

                    <div class="surface surface--nested">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Performance</p>
                                <h4>Equity Curve</h4>
                            </div>
                        </div>
                        <EquityChart points={latestResult.equity_curve} />
                    </div>

                    <ResearchRunValidation
                        validation={latestResult.validation}
                        warnings={latestResult.warnings}
                    />

                    {#if Object.keys(latestResult.baselines).length}
                        <div class="surface surface--nested">
                            <div class="surface-header">
                                <div>
                                    <p class="eyebrow">Comparisons</p>
                                    <h4>Baseline Metrics</h4>
                                </div>
                            </div>
                            <div class="table-wrap">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Baseline</th>
                                            <th>Total Return</th>
                                            <th>Sharpe</th>
                                            <th>Max Drawdown</th>
                                            <th>Turnover</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {#each Object.entries(latestResult.baselines) as [baseline, metrics]}
                                            <tr>
                                                <td>{baseline}</td>
                                                <td
                                                    >{metrics.total_return?.toFixed(
                                                        3,
                                                    ) ?? "N/A"}</td
                                                >
                                                <td
                                                    >{metrics.sharpe?.toFixed(3) ??
                                                        "N/A"}</td
                                                >
                                                <td
                                                    >{metrics.max_drawdown?.toFixed(
                                                        3,
                                                    ) ?? "N/A"}</td
                                                >
                                                <td
                                                    >{metrics.turnover?.toFixed(
                                                        3,
                                                    ) ?? "N/A"}</td
                                                >
                                            </tr>
                                        {/each}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    {/if}

                    <ResearchRunSignals signals={latestResult.signals} />
                {:else}
                    <div class="result-placeholder">
                        <strong>No results yet</strong>
                        <p>
                            Build the workflow, submit it once, then metrics,
                            signals, and validation will appear here.
                        </p>
                    </div>
                {/if}

                <div class="stage-actions">
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => (activeStage = latestResult ? "validation" : "data")}
                    >
                        {latestResult ? "Back to Validation" : "Back to Start"}
                    </button>
                </div>
            </div>
        {/if}

        <details
            class="surface advanced-shell"
            open={isAdvancedOpen}
            ontoggle={(event) =>
                (isAdvancedOpen = (event.currentTarget as HTMLDetailsElement)
                    .open)}
        >
            <summary>Advanced details</summary>
            <div class="advanced-shell__content">
                <div class="advanced-grid">
                    <div class="surface surface--nested">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Saved Run</p>
                                <h4>Load a persisted record</h4>
                            </div>
                        </div>
                        <div class="lookup-row">
                            <input
                                bind:value={runLookupId}
                                placeholder="Paste a run ID"
                            />
                            <button
                                type="button"
                                onclick={submitLookup}
                                disabled={!runLookupId.trim() || isRunLoading}
                            >
                                {isRunLoading ? "Loading..." : "Load"}
                            </button>
                        </div>
                        {#if recordError}
                            <p class="muted">{recordError}</p>
                        {:else if researchRunRecord}
                            <div class="mini-grid">
                                <div>
                                    <strong>Status</strong>
                                    <span>{researchRunRecord.status}</span>
                                </div>
                                <div>
                                    <strong>Selection Mode</strong>
                                    <span
                                        >{formatDisplayValue(
                                            researchRunRecord.runtime_mode,
                                        )}</span
                                    >
                                </div>
                                <div>
                                    <strong>Comparison State</strong>
                                    <span
                                        >{researchRunRecord.comparison_eligibility ??
                                            "N/A"}</span
                                    >
                                </div>
                                <div>
                                    <strong>Execution Ratio</strong>
                                    <span
                                        >{formatRatio(
                                            researchRunRecord.execution_universe_ratio,
                                        )}</span
                                    >
                                </div>
                            </div>
                            <div class="metadata-grid">
                                <div>
                                    <p class="eyebrow">Config Sources</p>
                                    <pre>{serialize(
                                            researchRunRecord.config_sources,
                                        )}</pre>
                                </div>
                                <div>
                                    <p class="eyebrow">Fallback Audit</p>
                                    <pre>{serialize(
                                            researchRunRecord.fallback_audit,
                                        )}</pre>
                                </div>
                                <div>
                                    <p class="eyebrow">Version Pack</p>
                                    <pre>{serialize({
                                            threshold_policy_version:
                                                researchRunRecord.threshold_policy_version,
                                            price_basis_version:
                                                researchRunRecord.price_basis_version,
                                            benchmark_comparability_gate:
                                                researchRunRecord.benchmark_comparability_gate,
                                            comparison_eligibility:
                                                researchRunRecord.comparison_eligibility,
                                            factor_catalog_version:
                                                researchRunRecord.factor_catalog_version,
                                            external_lineage_version:
                                                researchRunRecord.external_lineage_version,
                                            cluster_snapshot_version:
                                                researchRunRecord.cluster_snapshot_version,
                                            simulation_adapter_version:
                                                researchRunRecord.simulation_adapter_version,
                                            live_control_version:
                                                researchRunRecord.live_control_version,
                                            adaptive_contract_version:
                                                researchRunRecord.adaptive_contract_version,
                                            version_pack_status:
                                                researchRunRecord.version_pack_status,
                                        })}</pre>
                                </div>
                            </div>
                        {:else}
                            <p class="muted">
                                Load a run when you need registry,
                                config-source, or fallback-audit details.
                            </p>
                        {/if}
                    </div>

                    <div class="surface surface--nested">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">System</p>
                                <h4>Health and readiness</h4>
                            </div>
                            {#if healthState.isHealthLoading}
                                <span class="muted">Checking...</span>
                            {:else if healthState.health}
                                <span class="muted"
                                    >{healthState.health.status} / {healthState
                                        .health.version}</span
                                >
                            {/if}
                        </div>
                        {#if healthState.healthError}
                            <p class="muted">{healthState.healthError}</p>
                        {:else if healthState.health}
                            <p class="muted">{healthState.health.service}</p>
                        {/if}

                        {#if gateState.gateError}
                            <p class="muted">{gateState.gateError}</p>
                        {:else if gateState.gates.length}
                            <div class="gate-grid">
                                {#each gateState.gates as gate}
                                    {@const summary = summarizeGate(gate)}
                                    <article class="gate-card">
                                        <div class="gate-card__header">
                                            <div>
                                                <p class="eyebrow">
                                                    Readiness Check
                                                </p>
                                                <h5>
                                                    {getGateTitle(gate.gate_id)}
                                                </h5>
                                            </div>
                                            <span
                                                class:gate-status={true}
                                                class:gate-status--pass={gate.overall_status ===
                                                    "pass"}
                                                class:gate-status--attention={gate.overall_status !==
                                                    "pass"}
                                            >
                                                {toLabel(gate.overall_status)}
                                            </span>
                                        </div>
                                        <div class="mini-grid">
                                            <div>
                                                <strong>Metrics</strong>
                                                <span
                                                    >{summary.passedMetrics} / {summary.totalMetrics}
                                                    passing</span
                                                >
                                            </div>
                                            <div>
                                                <strong>Artifacts</strong>
                                                <span
                                                    >{summary.passedArtifacts} / {summary.totalArtifacts}
                                                    ready</span
                                                >
                                            </div>
                                        </div>
                                    </article>
                                {/each}
                            </div>
                        {:else}
                            <p class="muted">
                                Readiness summaries are not available yet.
                            </p>
                        {/if}
                    </div>
                </div>
            </div>
        </details>
    </div>
</WorkspaceSection>

<style lang="scss">
    .studio-shell,
    .stage-strip,
    .module-grid,
    .group,
    .feature-list,
    .feature-row,
    .baseline-list,
    .lookup-row,
    .mini-grid,
    .metadata-grid,
    .gate-grid,
    .advanced-grid,
    .advanced-shell__content {
        display: grid;
        gap: 1rem;
    }

    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }

    .surface--lead {
        background:
            linear-gradient(
                135deg,
                rgba(17, 34, 56, 0.98),
                rgba(7, 16, 28, 0.9)
            ),
            rgba(15, 23, 42, 0.62);
    }

    .surface--nested {
        background: rgba(2, 6, 23, 0.42);
    }

    .surface--results {
        display: grid;
        gap: 1.1rem;
    }

    .surface-header,
    .gate-card__header,
    .submit-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
    }

    .surface-header--lead {
        align-items: flex-start;
        flex-wrap: wrap;
    }

    .lead-summary {
        display: grid;
        gap: 0.2rem;
        min-width: min(100%, 22rem);
        padding: 0.85rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(125, 211, 252, 0.12);
        background: rgba(7, 16, 28, 0.58);
    }

    .surface-note,
    .muted,
    .run-id,
    .summary-chip span,
    .result-placeholder p,
    .info-card p {
        color: var(--muted);
    }

    .eyebrow {
        margin: 0 0 0.3rem;
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    h3,
    h4,
    h5,
    strong,
    p {
        margin: 0;
    }

    .ghost-link {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 2.7rem;
        padding: 0.7rem 1rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        color: var(--text);
        text-decoration: none;
        background: rgba(2, 6, 23, 0.54);
    }

    .stage-strip {
        grid-template-columns: repeat(5, minmax(0, 1fr));
        align-items: stretch;
    }

    .stage-pill {
        display: grid;
        gap: 0.25rem;
        text-align: left;
        padding: 0.9rem 1rem;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(7, 16, 28, 0.42);
    }

    .stage-pill--active {
        border-color: rgba(245, 158, 11, 0.42);
        background: linear-gradient(
            180deg,
            rgba(66, 32, 6, 0.42),
            rgba(7, 16, 28, 0.52)
        );
        box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.2);
    }

    .stage-pill:disabled {
        cursor: not-allowed;
        opacity: 0.45;
    }

    .stage-pill span {
        color: var(--accent-primary);
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .stage-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.75rem;
        margin-top: 1rem;
        flex-wrap: wrap;
    }

    .group.one {
        grid-template-columns: 1fr;
    }

    .group.two,
    .metadata-grid,
    .advanced-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .group.three {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .group.four,
    .feature-row {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .wide,
    .full {
        grid-column: 1 / -1;
    }

    .module-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .module-card {
        display: grid;
        gap: 0.5rem;
        text-align: left;
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(2, 6, 23, 0.52);
        cursor: pointer;
    }

    .module-card--active {
        border-color: rgba(245, 158, 11, 0.46);
        box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.24);
        background: linear-gradient(
            180deg,
            rgba(66, 32, 6, 0.56),
            rgba(2, 6, 23, 0.52)
        );
    }

    .module-card span,
    .module-card p {
        color: var(--muted);
    }

    .module-section,
    .module-fields {
        margin-top: 0.25rem;
    }

    .info-card,
    .summary-chip,
    .result-placeholder {
        display: grid;
        gap: 0.4rem;
        padding: 0.95rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(125, 211, 252, 0.12);
        background: rgba(8, 21, 35, 0.52);
    }

    .info-card a {
        color: var(--accent-primary);
    }

    .feature-row,
    .baseline-list {
        gap: 0.85rem;
    }

    .baseline-list {
        grid-template-columns: 1fr;
        padding-top: 0.35rem;
    }

    label {
        display: grid;
        gap: 0.35rem;
    }

    span {
        color: var(--muted);
        font-size: 0.82rem;
    }

    input,
    select,
    button,
    summary {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }

    button {
        cursor: pointer;
    }

    .checkbox,
    .toggle {
        display: flex;
        gap: 0.75rem;
        align-items: center;
    }

    .checkbox input,
    .toggle input {
        width: auto;
        padding: 0;
    }

    .secondary {
        background: rgba(30, 41, 59, 0.9);
    }

    .danger {
        align-self: end;
        background: rgba(127, 29, 29, 0.9);
    }

    .submit {
        background: linear-gradient(135deg, #f59e0b, #ea580c);
        color: #0f172a;
        font-weight: 700;
    }

    .submit-row {
        margin-top: 1rem;
    }

    .status-banner,
    .error-banner {
        display: grid;
        gap: 0.25rem;
        padding: 0.9rem 1rem;
        border-radius: 18px;
    }

    .status-banner {
        border: 1px solid rgba(125, 211, 252, 0.24);
        background: rgba(8, 47, 73, 0.42);
    }

    .error-banner {
        border: 1px solid rgba(248, 113, 113, 0.28);
        background: rgba(69, 10, 10, 0.34);
    }

    .result-placeholder {
        min-height: 7rem;
        align-content: center;
    }

    .table-wrap {
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    th,
    td {
        text-align: left;
        padding: 0.8rem 0.5rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        white-space: nowrap;
    }

    .advanced-config {
        display: grid;
        gap: 1rem;
        margin-top: 0.2rem;
    }

    .advanced-config summary,
    .advanced-shell summary {
        list-style: none;
        cursor: pointer;
        font-weight: 600;
    }

    .advanced-config summary::-webkit-details-marker,
    .advanced-shell summary::-webkit-details-marker {
        display: none;
    }

    .advanced-grid {
        margin-top: 1rem;
    }

    .lookup-row {
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .mini-grid {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }

    .mini-grid div {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.66);
    }

    pre {
        margin: 0;
        padding: 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
        white-space: pre-wrap;
        word-break: break-word;
        font-family: var(--mono);
        font-size: 0.78rem;
    }

    .gate-card {
        display: grid;
        gap: 0.85rem;
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(8, 21, 35, 0.5);
    }

    .gate-status {
        padding: 0.35rem 0.65rem;
        border-radius: 999px;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .gate-status--pass {
        background: rgba(34, 197, 94, 0.16);
        color: #86efac;
    }

    .gate-status--attention {
        background: rgba(245, 158, 11, 0.14);
        color: #fcd34d;
    }

    small {
        color: #fca5a5;
    }

    @media (max-width: 1200px) {
        .stage-strip,
        .module-grid,
        .group.two,
        .group.three,
        .group.four,
        .feature-row,
        .metadata-grid,
        .advanced-grid {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 720px) {
        .surface-header,
        .stage-actions,
        .submit-row {
            align-items: stretch;
            flex-direction: column;
        }

        .lookup-row {
            grid-template-columns: 1fr;
        }
    }
</style>
