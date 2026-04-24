<script lang="ts">
    import { createMutation, createQuery } from "@tanstack/svelte-query";
    import { createEventDispatcher } from "svelte";

    import {
        ApiError,
        createResearchRun,
        fetchResearchFeatureRegistry,
    } from "../api";
    import {
        availableBaselines,
        DEFAULT_BUNDLE_VERSION,
        DEFAULT_RUNTIME_MODE,
        VNEXT_SPEC_MODE,
    } from "../state/predictionPipeline";
    import {
        createFeatureRegistryQueryOptions,
        createIndicatorRow,
        getAllowedSources,
        getFeatureDefinitions,
        updateIndicatorFeatureName,
    } from "../state/featureRegistry";
    import {
        applyTemplateToDraft,
        buildResearchRunPayloadFromWorkflow,
        createDefaultResearchWorkflowDraft,
        createWorkflowSubmissionSummary,
        getCapabilityDefinition,
        getModelFamilyById,
        getModelVariantById,
        modelFamilies,
        parseScoringFactorIds,
        parseSymbols,
        researchCapabilityRegistry,
        researchTemplates,
        updateModelFamily,
        validateResearchWorkflow,
        withCapabilityToggled,
    } from "../state/researchWorkflow";
    import type {
        AppError,
        CapabilityReadinessState,
        ResearchCapabilityId,
        ResearchFeatureRow,
        ResearchSubmissionSummary,
        ResearchWorkflowDraft,
        ResearchWorkflowStageId,
        ResearchRunResponse,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import CapabilityCard from "./research/CapabilityCard.svelte";

    export let capabilityReadiness: Record<
        ResearchCapabilityId,
        CapabilityReadinessState
    >;

    const dispatch = createEventDispatcher<{
        runcreated: {
            result: ResearchRunResponse;
            summary: ResearchSubmissionSummary;
        };
    }>();

    type StageSummary = {
        id: ResearchWorkflowStageId;
        label: string;
        title: string;
        summary: string;
    };

    const stageOrder: ResearchWorkflowStageId[] = [
        "universe",
        "signal_sources",
        "model_family",
        "evaluation",
        "review",
    ];

    let draft: ResearchWorkflowDraft = createDefaultResearchWorkflowDraft();
    let errors: Record<string, string> = {};
    let submitError: AppError | null = null;
    let activeStage: ResearchWorkflowStageId = "universe";
    let lastSubmittedSummary: ResearchSubmissionSummary | null = null;

    const optionLabels: Record<string, string> = {
        runtime_compatibility_mode: "Manual Threshold Mode",
        vnext_spec_mode: "Standard Research Mode",
        open_to_open: "Open to Open",
        close_to_close: "Close to Close",
        open_to_close: "Open to Close",
        research_only: "Research Only",
        simulation_internal_v1: "Internal Simulation",
        live_stub_v1: "Live Stub",
        shadow: "Shadow",
        candidate: "Candidate",
    };

    const mutation = createMutation(() => ({
        mutationFn: createResearchRun,
        onSuccess: (data) => {
            submitError = null;
            dispatch("runcreated", {
                result: data,
                summary:
                    lastSubmittedSummary ??
                    createWorkflowSubmissionSummary(draft),
            });
        },
        onError: (error) => {
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

    const featureRegistryQuery = createQuery(() =>
        createFeatureRegistryQueryOptions(fetchResearchFeatureRegistry),
    );

    const getOptionLabel = (value: string) => optionLabels[value] ?? value;
    const featureRegistry = () => featureRegistryQuery.data?.features;

    const getReadiness = (capabilityId: ResearchCapabilityId) =>
        capabilityReadiness[capabilityId] ?? {
            capabilityId,
            status: "not_implemented",
            summary: "Capability readiness is unavailable.",
            gateId: null,
            overallStatus: null,
        };

    const getCapabilityLabel = (capabilityId: ResearchCapabilityId) =>
        getCapabilityDefinition(capabilityId).label;

    const getCapabilityIdsByStage = (stageId: ResearchWorkflowStageId) =>
        researchCapabilityRegistry
            .filter((capability) => capability.stage === stageId)
            .map((capability) => capability.id);

    const isCapabilityToggleDisabled = (capabilityId: ResearchCapabilityId) => {
        const readiness = getReadiness(capabilityId);
        if (capabilityId === "technical_indicators") {
            return true;
        }
        return (
            readiness.status === "gated" ||
            readiness.status === "not_implemented"
        );
    };

    const addIndicator = () => {
        draft = {
            ...draft,
            signalSources: {
                ...draft.signalSources,
                indicatorRows: [
                    ...draft.signalSources.indicatorRows,
                    createIndicatorRow(
                        `workflow-feature-${Date.now()}`,
                        featureRegistry(),
                    ),
                ],
            },
        };
    };

    const removeIndicator = (id: string) => {
        if (draft.signalSources.indicatorRows.length === 1) {
            return;
        }

        draft = {
            ...draft,
            signalSources: {
                ...draft.signalSources,
                indicatorRows: draft.signalSources.indicatorRows.filter(
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
            signalSources: {
                ...draft.signalSources,
                indicatorRows: draft.signalSources.indicatorRows.map(
                    (feature) =>
                        feature.id === id
                            ? key === "name"
                                ? updateIndicatorFeatureName(
                                      feature,
                                      String(value),
                                      featureRegistry(),
                                  )
                                : { ...feature, [key]: value }
                            : feature,
                ),
            },
        };
    };

    const handleTemplateSelect = (templateId: typeof draft.templateId) => {
        draft = applyTemplateToDraft(draft, templateId);
        errors = {};
        submitError = null;
        activeStage = "universe";
    };

    const handleCapabilityToggle = (
        capabilityId: ResearchCapabilityId,
        checked: boolean,
    ) => {
        draft = withCapabilityToggled(draft, capabilityId, checked);
        errors = {
            ...errors,
            [`${capabilityId}Gate`]: "",
        };
    };

    const handleModelFamilySelect = (
        familyId: typeof draft.modelFamily.familyId,
    ) => {
        draft = updateModelFamily(draft, familyId);
    };

    const toggleBaseline = (baseline: (typeof availableBaselines)[number]) => {
        const baselines = draft.evaluation.baselines.includes(baseline)
            ? draft.evaluation.baselines.filter((item) => item !== baseline)
            : [...draft.evaluation.baselines, baseline];

        draft = {
            ...draft,
            evaluation: {
                ...draft.evaluation,
                baselines,
            },
        };
    };

    const moveStage = (direction: -1 | 1) => {
        const currentIndex = stageOrder.indexOf(activeStage);
        const nextIndex = currentIndex + direction;
        if (nextIndex < 0 || nextIndex >= stageOrder.length) {
            return;
        }
        activeStage = stageOrder[nextIndex];
    };

    const openStage = (stageId: ResearchWorkflowStageId) => {
        activeStage = stageId;
    };

    const submitWorkflow = () => {
        const nextErrors = validateResearchWorkflow(draft, capabilityReadiness);
        errors = nextErrors;

        if (Object.keys(nextErrors).length > 0) {
            activeStage = "review";
            return;
        }

        submitError = null;
        lastSubmittedSummary = createWorkflowSubmissionSummary(draft);
        mutation.mutate(buildResearchRunPayloadFromWorkflow(draft));
    };

    $: stageSummaries = [
        {
            id: "universe",
            label: "01",
            title: "Dataset",
            summary: `${draft.universe.market} / ${
                parseSymbols(draft.universe.symbolsInput).length
            } symbol(s)`,
        },
        {
            id: "signal_sources",
            label: "02",
            title: "Features",
            summary: (
                Object.entries(draft.capabilities) as Array<
                    [ResearchCapabilityId, boolean]
                >
            )
                .filter(([, enabled]) => enabled)
                .map(([capabilityId]) => getCapabilityLabel(capabilityId))
                .join(" + "),
        },
        {
            id: "model_family",
            label: "03",
            title: "Prediction Task",
            summary: `${getModelFamilyById(draft.modelFamily.familyId).label} / ${
                getModelVariantById(draft.modelFamily.variantId).label
            }`,
        },
        {
            id: "evaluation",
            label: "04",
            title: "Diagnostics and Backtest",
            summary: draft.capabilities.simulation_execution
                ? `${getOptionLabel(draft.evaluation.executionRoute)} / ${
                      draft.evaluation.enableValidation
                          ? draft.evaluation.validationMethod
                          : "validation off"
                  }`
                : `${draft.evaluation.validationMethod} / research only`,
        },
        {
            id: "review",
            label: "05",
            title: "Review",
            summary:
                Object.keys(errors).length > 0
                    ? `${Object.keys(errors).length} issue(s) to resolve`
                    : "Ready to submit the workflow",
        },
    ] satisfies StageSummary[];

    $: reviewErrors = validateResearchWorkflow(draft, capabilityReadiness);
    $: activeCapabilities = (
        Object.entries(draft.capabilities) as Array<
            [ResearchCapabilityId, boolean]
        >
    )
        .filter(([, isEnabled]) => isEnabled)
        .map(([capabilityId]) => capabilityId);
    $: activeTemplate = researchTemplates.find(
        (template) => template.id === draft.templateId,
    );
    $: activeModelFamily = getModelFamilyById(draft.modelFamily.familyId);
    $: activeTemplateCapabilityLabels =
        activeTemplate?.defaultCapabilities.map((capabilityId) =>
            getCapabilityLabel(capabilityId),
        ) ?? [];
</script>

<WorkspaceSection
    id="research-workspace"
    eyebrow="Experiment Builder"
    title="Run a baseline TW daily experiment without editing an API payload."
    description="Move from dataset and features into prediction task, diagnostics, backtest, and review."
>
    <div class="research-shell">
        <section class="surface surface--intro">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Baseline</p>
                    <h3>Start from the v1 research loop</h3>
                </div>
                <p class="muted">
                    Advanced execution, adaptive, peer, factor, and tick
                    archive modules stay out of the main builder.
                </p>
            </div>

            <div class="template-grid">
                {#each researchTemplates as template}
                    <button
                        type="button"
                        class:template-card={true}
                        class:template-card--active={template.id ===
                            draft.templateId}
                        onclick={() => handleTemplateSelect(template.id)}
                    >
                        <span>{template.label}</span>
                        <strong>{template.summary}</strong>
                    </button>
                {/each}
            </div>
        </section>

        <section class="surface surface--stages">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Workflow</p>
                    <h3>
                        {stageSummaries.find(
                            (stage) => stage.id === activeStage,
                        )?.label}
                        {stageSummaries.find(
                            (stage) => stage.id === activeStage,
                        )?.title}
                    </h3>
                </div>
                <p class="muted">
                    {stageSummaries.find((stage) => stage.id === activeStage)
                        ?.summary}
                </p>
            </div>

            <div class="stage-strip">
                {#each stageSummaries as stage}
                    <button
                        type="button"
                        class:stage-pill={true}
                        class:stage-pill--active={stage.id === activeStage}
                        onclick={() => openStage(stage.id)}
                    >
                        <span>{stage.label}</span>
                        <strong>{stage.title}</strong>
                        <small>{stage.summary}</small>
                    </button>
                {/each}
            </div>
        </section>

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

        {#if mutation.isPending}
            <div class="surface status-surface" aria-live="polite">
                <strong>Compiling research workflow</strong>
                <span class="muted">
                    The current workflow is being translated into the existing
                    research run contract.
                </span>
            </div>
        {/if}

        {#if activeStage === "universe"}
            <section class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">01 Universe</p>
                        <h3>Choose the market and backtest window</h3>
                    </div>
                    <button
                        type="button"
                        class="secondary"
                        onclick={() =>
                            (draft = createDefaultResearchWorkflowDraft(
                                draft.templateId,
                            ))}
                    >
                        Reset Template
                    </button>
                </div>

                <div class="form-grid form-grid--four">
                    <label>
                        <span>Market</span>
                        <select bind:value={draft.universe.market}>
                            <option value="TW">TW</option>
                            <option value="US">US</option>
                        </select>
                    </label>
                    <label class="form-grid__wide">
                        <span>Symbols</span>
                        <input
                            bind:value={draft.universe.symbolsInput}
                            placeholder="2330, 2317, AAPL"
                        />
                        {#if errors.symbolsInput}<small
                                >{errors.symbolsInput}</small
                            >{/if}
                    </label>
                    <label>
                        <span>Start Date</span>
                        <input
                            type="date"
                            bind:value={draft.universe.startDate}
                        />
                    </label>
                    <label>
                        <span>End Date</span>
                        <input
                            type="date"
                            bind:value={draft.universe.endDate}
                        />
                    </label>
                    <label>
                        <span>Return Target</span>
                        <select bind:value={draft.universe.returnTarget}>
                            <option value="open_to_open">Open to Open</option>
                            <option value="close_to_close"
                                >Close to Close</option
                            >
                            <option value="open_to_close">Open to Close</option>
                        </select>
                    </label>
                    <label>
                        <span>Horizon Days</span>
                        <input
                            type="number"
                            min="1"
                            bind:value={draft.universe.horizonDays}
                        />
                        {#if errors.horizonDays}<small
                                >{errors.horizonDays}</small
                            >{/if}
                    </label>
                </div>

                {#if errors.dateRange}<small>{errors.dateRange}</small>{/if}

                <div class="stage-actions">
                    <button
                        type="button"
                        class="submit"
                        onclick={() => moveStage(1)}
                    >
                        Continue to Features
                    </button>
                </div>
            </section>
        {/if}

        {#if activeStage === "signal_sources"}
            <section class="surface">
                <div class="surface-header surface-header--stack">
                    <div>
                        <p class="eyebrow">02 Features</p>
                        <h3>Choose the baseline feature set</h3>
                    </div>
                    <p class="muted">
                        {activeTemplate?.label} uses
                        {" "}
                        {activeTemplateCapabilityLabels.join(", ")} as the
                        core model input.
                    </p>
                </div>

                <div class="capability-grid capability-grid--full">
                    <CapabilityCard
                        capability={getCapabilityDefinition(
                            "technical_indicators",
                        )}
                        readiness={getReadiness("technical_indicators")}
                        isEnabled={true}
                        isToggleDisabled={true}
                        titleSuffix=" (Core)"
                    >
                        <div class="module-section">
                            <div class="surface-header">
                                <div>
                                    <p class="eyebrow">Core Inputs</p>
                                    <h4>Indicator rows</h4>
                                </div>
                                <button
                                    type="button"
                                    class="secondary"
                                    onclick={addIndicator}
                                >
                                    Add Indicator
                                </button>
                            </div>
                            <div class="feature-list">
                                {#each draft.signalSources.indicatorRows as feature}
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
                                                {#each getFeatureDefinitions(featureRegistry()) as definition}
                                                    <option
                                                        value={definition.name}
                                                        >{definition.name}</option
                                                    >
                                                {/each}
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
                                                {#each getAllowedSources(feature.name, featureRegistry()) as source}
                                                    <option value={source}
                                                        >{source}</option
                                                    >
                                                {/each}
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
                                            onclick={() =>
                                                removeIndicator(feature.id)}
                                        >
                                            Remove
                                        </button>
                                        {#if errors[`feature-${feature.id}`]}
                                            <small class="form-grid__wide">
                                                {errors[
                                                    `feature-${feature.id}`
                                                ]}
                                            </small>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        </div>
                    </CapabilityCard>
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
                        onclick={() => moveStage(1)}
                    >
                        Continue to Prediction Task
                    </button>
                </div>
            </section>
        {/if}

        {#if activeStage === "model_family"}
            <section class="surface">
                <div class="surface-header surface-header--stack">
                    <div>
                        <p class="eyebrow">03 Prediction Task</p>
                        <h3>
                            Pick the regression model for this baseline study
                        </h3>
                    </div>
                    <p class="muted">
                        Classification is specified for future work. This code
                        path runs regression diagnostics first.
                    </p>
                </div>

                <div class="family-grid">
                    {#each modelFamilies as family}
                        <button
                            type="button"
                            class:family-card={true}
                            class:family-card--active={family.id ===
                                draft.modelFamily.familyId}
                            disabled={family.status !== "available"}
                            onclick={() => handleModelFamilySelect(family.id)}
                        >
                            <span
                                >{family.status === "available"
                                    ? "Available"
                                    : "Future"}</span
                            >
                            <strong>{family.label}</strong>
                            <p>{family.summary}</p>
                        </button>
                    {/each}
                </div>

                <div class="variant-grid">
                    {#each activeModelFamily.variantIds.map( (variantId) => getModelVariantById(variantId), ) as variant}
                        <button
                            type="button"
                            class:variant-card={true}
                            class:variant-card--active={variant.id ===
                                draft.modelFamily.variantId}
                            disabled={variant.status !== "available"}
                            onclick={() =>
                                (draft = {
                                    ...draft,
                                    modelFamily: {
                                        ...draft.modelFamily,
                                        variantId: variant.id,
                                    },
                                })}
                        >
                            <span
                                >{variant.status === "available"
                                    ? "Supported"
                                    : "Blocked"}</span
                            >
                            <strong>{variant.label}</strong>
                            <p>{variant.summary}</p>
                        </button>
                    {/each}
                </div>

                {#if errors.modelVariant}<small>{errors.modelVariant}</small
                    >{/if}

                <details class="advanced-config">
                    <summary>Research policy and selection controls</summary>
                    <div class="form-grid form-grid--four">
                        <label>
                            <span>Selection Mode</span>
                            <select bind:value={draft.modelFamily.runtimeMode}>
                                <option value={DEFAULT_RUNTIME_MODE}>
                                    {getOptionLabel(DEFAULT_RUNTIME_MODE)}
                                </option>
                                <option value={VNEXT_SPEC_MODE}>
                                    {getOptionLabel(VNEXT_SPEC_MODE)}
                                </option>
                            </select>
                            {#if errors.runtime}<small>{errors.runtime}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Default Bundle</span>
                            <select
                                value={draft.modelFamily.defaultBundleVersion ??
                                    ""}
                                disabled={draft.modelFamily.runtimeMode !==
                                    VNEXT_SPEC_MODE}
                                onchange={(event) =>
                                    (draft = {
                                        ...draft,
                                        modelFamily: {
                                            ...draft.modelFamily,
                                            defaultBundleVersion: ((
                                                event.currentTarget as HTMLSelectElement
                                            ).value ||
                                                null) as typeof draft.modelFamily.defaultBundleVersion,
                                        },
                                    })}
                            >
                                <option value="">None</option>
                                <option value={DEFAULT_BUNDLE_VERSION}>
                                    Default Research Spec
                                </option>
                            </select>
                        </label>
                        <label>
                            <span>Threshold</span>
                            <input
                                type="number"
                                step="0.001"
                                bind:value={draft.modelFamily.threshold}
                            />
                            {#if errors.threshold}<small
                                    >{errors.threshold}</small
                                >{/if}
                        </label>
                        <label>
                            <span>Top N</span>
                            <input
                                type="number"
                                min="1"
                                bind:value={draft.modelFamily.topN}
                            />
                            {#if errors.topN}<small>{errors.topN}</small>{/if}
                        </label>
                        <label class="toggle">
                            <span>Allow Proactive Sells</span>
                            <input
                                type="checkbox"
                                bind:checked={
                                    draft.modelFamily.allowProactiveSells
                                }
                            />
                        </label>
                    </div>
                </details>

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
                        onclick={() => moveStage(1)}
                    >
                        Continue to Diagnostics
                    </button>
                </div>
            </section>
        {/if}

        {#if activeStage === "evaluation"}
            <section class="surface">
                <div class="surface-header surface-header--stack">
                    <div>
                        <p class="eyebrow">04 Diagnostics and Backtest</p>
                        <h3>
                            Decide validation, baselines, and offline backtest
                            assumptions
                        </h3>
                    </div>
                    <p class="muted">
                        The run remains research-only. Model diagnostics are
                        reviewed before strategy metrics.
                    </p>
                </div>

                <div class="form-grid form-grid--three">
                    <label class="toggle">
                        <span>Validation Enabled</span>
                        <input
                            type="checkbox"
                            bind:checked={draft.evaluation.enableValidation}
                        />
                    </label>
                    <label>
                        <span>Validation Method</span>
                        <select bind:value={draft.evaluation.validationMethod}>
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
                        <span>Baselines</span>
                        <div class="baseline-list">
                            {#each availableBaselines as baseline}
                                <label class="checkbox">
                                    <input
                                        type="checkbox"
                                        checked={draft.evaluation.baselines.includes(
                                            baseline,
                                        )}
                                        onchange={() =>
                                            toggleBaseline(baseline)}
                                    />
                                    <span>{baseline}</span>
                                </label>
                            {/each}
                        </div>
                    </label>
                </div>

                {#if draft.evaluation.enableValidation}
                    <div class="form-grid form-grid--three">
                        <label>
                            <span>Validation Splits</span>
                            <input
                                type="number"
                                min="1"
                                bind:value={draft.evaluation.validationSplits}
                            />
                            {#if errors.validationSplits}
                                <small>{errors.validationSplits}</small>
                            {/if}
                        </label>
                        <label>
                            <span>Validation Test Size</span>
                            <input
                                type="number"
                                min="0.01"
                                max="0.99"
                                step="0.01"
                                bind:value={draft.evaluation.validationTestSize}
                            />
                            {#if errors.validationTestSize}
                                <small>{errors.validationTestSize}</small>
                            {/if}
                        </label>
                        <label>
                            <span>Portfolio AUM</span>
                            <input
                                type="number"
                                min="0"
                                step="100000"
                                bind:value={draft.evaluation.portfolioAum}
                                placeholder="Optional"
                            />
                            {#if errors.portfolioAum}<small
                                    >{errors.portfolioAum}</small
                                >{/if}
                        </label>
                    </div>
                {/if}

                <label class="toggle">
                    <span>Save as monitoring run</span>
                    <input
                        type="checkbox"
                        bind:checked={draft.evaluation.recordAsMonitorRun}
                    />
                </label>

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
                        onclick={() => moveStage(1)}
                    >
                        Continue to Review
                    </button>
                </div>
            </section>
        {/if}

        {#if activeStage === "review"}
            <section class="surface">
                <div class="surface-header surface-header--stack">
                    <div>
                        <p class="eyebrow">05 Review</p>
                        <h3>Check the workflow before submitting it</h3>
                    </div>
                    <p class="muted">
                        The workflow will still submit to the current
                        `/api/v1/research/runs` contract. This screen turns the
                        contract details into a research-facing checklist.
                    </p>
                </div>

                <div class="review-grid">
                    <div class="review-card">
                        <span>Template</span>
                        <strong>{activeTemplate?.label}</strong>
                        <p>{activeTemplate?.summary}</p>
                    </div>
                    <div class="review-card">
                        <span>Model Family</span>
                        <strong>{activeModelFamily.label}</strong>
                        <p>
                            {getModelVariantById(draft.modelFamily.variantId)
                                .label}
                        </p>
                    </div>
                    <div class="review-card">
                        <span>Capabilities</span>
                        <strong>{activeCapabilities.length}</strong>
                        <p>
                            {activeCapabilities
                                .map((capabilityId) =>
                                    getCapabilityLabel(capabilityId),
                                )
                                .join(", ")}
                        </p>
                    </div>
                    <div class="review-card">
                        <span>Evaluation</span>
                        <strong
                            >{getOptionLabel(
                                draft.evaluation.executionRoute,
                            )}</strong
                        >
                        <p>
                            {draft.evaluation.enableValidation
                                ? draft.evaluation.validationMethod
                                : "validation disabled"}
                        </p>
                    </div>
                </div>

                <div class="review-grid review-grid--secondary">
                    <div class="surface surface--nested">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Checklist</p>
                                <h4>Workflow blockers</h4>
                            </div>
                            <span class="muted"
                                >{Object.keys(reviewErrors).length} item(s)</span
                            >
                        </div>

                        {#if Object.keys(reviewErrors).length}
                            <ul class="issue-list">
                                {#each Object.entries(reviewErrors) as [, message]}
                                    <li>{message}</li>
                                {/each}
                            </ul>
                        {:else}
                            <p class="muted">
                                No blocking issues detected. This workflow is
                                ready to submit.
                            </p>
                        {/if}
                    </div>

                    <div class="surface surface--nested">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Payload Summary</p>
                                <h4>What the backend will receive</h4>
                            </div>
                        </div>
                        <div class="mini-grid">
                            <div>
                                <strong>Symbols</strong>
                                <span
                                    >{parseSymbols(
                                        draft.universe.symbolsInput,
                                    ).join(", ")}</span
                                >
                            </div>
                            <div>
                                <strong>Signal Sources</strong>
                                <span>{activeCapabilities.join(", ")}</span>
                            </div>
                            <div>
                                <strong>Tree Variant</strong>
                                <span
                                    >{getModelVariantById(
                                        draft.modelFamily.variantId,
                                    ).label}</span
                                >
                            </div>
                            <div>
                                <strong>Baselines</strong>
                                <span
                                    >{draft.evaluation.baselines.join(
                                        ", ",
                                    )}</span
                                >
                            </div>
                        </div>
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
                        onclick={submitWorkflow}
                        disabled={mutation.isPending}
                    >
                        {mutation.isPending
                            ? "Running Research..."
                            : "Run Research Workflow"}
                    </button>
                </div>
            </section>
        {/if}
    </div>
</WorkspaceSection>

<style lang="scss">
    .research-shell,
    .template-grid,
    .stage-strip,
    .capability-grid,
    .feature-list,
    .review-grid {
        display: grid;
        gap: var(--space-4);
    }

    .surface--intro,
    .surface--stages {
        gap: var(--space-4);
    }

    .surface--nested {
        background: rgba(5, 15, 26, 0.82);
        box-shadow: none;
    }

    .surface-header--stack {
        align-items: flex-start;
        flex-direction: column;
    }

    .template-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .template-card,
    .family-card,
    .variant-card {
        display: grid;
        gap: 0.55rem;
        text-align: left;
        padding: 1rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(6, 18, 30, 0.9);
    }

    .template-card--active,
    .family-card--active,
    .variant-card--active,
    .stage-pill--active {
        border-color: rgba(56, 189, 248, 0.38);
        box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.18);
        background: rgba(10, 32, 48, 0.94);
    }

    .template-card span,
    .family-card span,
    .variant-card span,
    .review-card span {
        color: var(--accent-primary);
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .template-card strong,
    .family-card strong,
    .variant-card strong,
    .review-card strong {
        font-size: 1rem;
        line-height: 1.4;
    }

    .family-card p,
    .variant-card p,
    .review-card p {
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
    }

    .stage-strip {
        grid-template-columns: repeat(5, minmax(0, 1fr));
    }

    .stage-pill {
        display: grid;
        gap: 0.35rem;
        text-align: left;
        padding: 0.95rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(6, 18, 30, 0.9);
    }

    .stage-pill span {
        color: var(--accent-primary);
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .stage-pill strong,
    .stage-pill small {
        margin: 0;
    }

    .stage-pill small {
        color: var(--muted);
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .form-grid,
    .feature-row,
    .family-grid,
    .variant-grid {
        display: grid;
        gap: var(--space-3);
    }

    .form-grid--three {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .form-grid--four {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .form-grid__wide {
        grid-column: 1 / -1;
    }

    .capability-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .capability-grid--full {
        grid-template-columns: 1fr;
    }

    .feature-row {
        grid-template-columns: repeat(5, minmax(0, 1fr));
        align-items: end;
        padding: 0.95rem;
        border-radius: var(--radius-md);
        background: rgba(4, 13, 23, 0.74);
    }

    .feature-row :global(button.danger) {
        min-height: 3.1rem;
    }

    .family-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .variant-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .advanced-config {
        display: grid;
        gap: var(--space-4);
    }

    .advanced-config summary {
        list-style: none;
        font-weight: 600;
        cursor: pointer;
    }

    .advanced-config summary::-webkit-details-marker {
        display: none;
    }

    .baseline-list {
        padding-top: 0.35rem;
    }

    .review-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .review-grid--secondary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .review-card {
        display: grid;
        gap: 0.5rem;
        padding: 1rem;
        border-radius: var(--radius-md);
        background: rgba(6, 18, 30, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .issue-list {
        margin: 0;
        padding-left: 1.1rem;
        color: #ffcad5;
    }

    .status-surface {
        gap: 0.35rem;
    }

    .stage-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.8rem;
        flex-wrap: wrap;
    }

    @media (max-width: 1200px) {
        .template-grid,
        .stage-strip,
        .capability-grid,
        .review-grid,
        .review-grid--secondary,
        .form-grid--three,
        .form-grid--four,
        .family-grid,
        .variant-grid,
        .feature-row {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 720px) {
        .stage-actions {
            align-items: stretch;
            flex-direction: column;
        }
    }
</style>
