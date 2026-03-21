<script lang="ts">
    import {
        DEFAULT_BUNDLE_VERSION,
        DEFAULT_RUNTIME_MODE,
        DEFAULT_THRESHOLD,
        DEFAULT_TOP_N,
        VNEXT_SPEC_MODE,
        availableBaselines,
        buildResearchRunPayload,
        createDefaultResearchRunFormState,
        parseSymbols,
    } from "../../state/researchRunForm";
    import type {
        BaselineName,
        ResearchFeatureRow,
        ResearchRunCreateRequest,
        ResearchRunFormState,
        RuntimeMode,
    } from "../../types";

    export let isSubmitting = false;
    export let onSubmit: (payload: ResearchRunCreateRequest) => void;

    let form: ResearchRunFormState = createDefaultResearchRunFormState();
    let errors: Record<string, string> = {};

    const runtimeUsesDefaults = () => form.runtimeMode === VNEXT_SPEC_MODE;

    const addFeature = () => {
        form.features = [
            ...form.features,
            {
                id: `feature-${Date.now()}`,
                name: "ma",
                window: 5,
                source: "close",
                shift: 1,
            },
        ];
    };

    const removeFeature = (id: string) => {
        if (form.features.length === 1) {
            return;
        }
        form.features = form.features.filter((feature) => feature.id !== id);
    };

    const updateFeature = <K extends keyof ResearchFeatureRow>(
        id: string,
        key: K,
        value: ResearchFeatureRow[K],
    ) => {
        form.features = form.features.map((feature) =>
            feature.id === id ? { ...feature, [key]: value } : feature,
        );
    };

    const toggleBaseline = (baseline: BaselineName) => {
        form.baselines = form.baselines.includes(baseline)
            ? form.baselines.filter((item) => item !== baseline)
            : [...form.baselines, baseline];
    };

    const handleRuntimeModeChange = (value: RuntimeMode) => {
        const previousMode = form.runtimeMode;
        form.runtimeMode = value;
        form.defaultBundleVersion =
            value === VNEXT_SPEC_MODE
                ? (form.defaultBundleVersion ?? DEFAULT_BUNDLE_VERSION)
                : null;
        if (
            previousMode === VNEXT_SPEC_MODE &&
            value === DEFAULT_RUNTIME_MODE
        ) {
            if (form.threshold === null) {
                form.threshold = DEFAULT_THRESHOLD;
            }
            if (form.topN === null) {
                form.topN = DEFAULT_TOP_N;
            }
        }
    };

    const validate = () => {
        const nextErrors: Record<string, string> = {};
        const symbols = parseSymbols(form.symbolsInput);

        if (!symbols.length) {
            nextErrors.symbolsInput = "Enter at least one symbol.";
        } else if (symbols.length !== new Set(symbols).size) {
            nextErrors.symbolsInput = "Duplicate symbols are not allowed.";
        }

        if (!form.startDate || !form.endDate) {
            nextErrors.dateRange = "Select both start and end dates.";
        } else if (form.startDate > form.endDate) {
            nextErrors.dateRange = "End date must be on or after start date.";
        }

        if (form.horizonDays < 1) {
            nextErrors.horizonDays = "Horizon must be at least 1 day.";
        }

        if (runtimeUsesDefaults()) {
            if (!form.defaultBundleVersion) {
                nextErrors.runtime =
                    "Default bundle is required in vnext spec mode.";
            }
            if (form.threshold !== null && form.threshold < 0) {
                nextErrors.threshold = "Threshold cannot be negative.";
            }
            if (form.topN !== null && form.topN < 1) {
                nextErrors.topN = "Top N must be at least 1.";
            }
        } else {
            if (form.threshold === null) {
                nextErrors.threshold =
                    "Threshold is required in compatibility mode.";
            } else if (form.threshold < 0) {
                nextErrors.threshold = "Threshold cannot be negative.";
            }
            if (form.topN === null) {
                nextErrors.topN = "Top N is required in compatibility mode.";
            } else if (form.topN < 1) {
                nextErrors.topN = "Top N must be at least 1.";
            }
        }

        if (form.slippage < 0 || form.fees < 0) {
            nextErrors.execution = "Fees and slippage cannot be negative.";
        }
        if (form.portfolioAum !== null && form.portfolioAum <= 0) {
            nextErrors.portfolioAum = "Portfolio AUM must be greater than 0.";
        }

        const uniqueFeatures = new Set<string>();
        form.features.forEach((feature) => {
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

        if (form.enableValidation) {
            if (form.validationSplits < 1) {
                nextErrors.validationSplits = "Splits must be at least 1.";
            }
            if (form.validationTestSize <= 0 || form.validationTestSize >= 1) {
                nextErrors.validationTestSize =
                    "Test size must be between 0 and 1.";
            }
        }

        errors = nextErrors;
        return Object.keys(nextErrors).length === 0;
    };

    const submitForm = () => {
        if (!validate()) {
            return;
        }
        onSubmit(buildResearchRunPayload(form));
    };

    const resetForm = () => {
        form = createDefaultResearchRunFormState();
        errors = {};
    };
</script>

<div class="panel">
    <div class="section-header">
        <div>
            <p class="eyebrow">Research Runs</p>
            <h3>Run Configuration</h3>
        </div>
        <button type="button" class="secondary" onclick={resetForm}
            >Reset</button
        >
    </div>

    <div class="group two">
        <label>
            <span>Market</span>
            <select bind:value={form.market}>
                <option value="TW">TW</option>
                <option value="US">US</option>
            </select>
        </label>
        <label class="wide">
            <span>Symbols</span>
            <input
                bind:value={form.symbolsInput}
                placeholder="2330, 2317, AAPL"
            />
            {#if errors.symbolsInput}<small>{errors.symbolsInput}</small>{/if}
        </label>
    </div>

    <div class="group three">
        <label>
            <span>Runtime Mode</span>
            <select
                value={form.runtimeMode}
                onchange={(event) =>
                    handleRuntimeModeChange(
                        (event.currentTarget as HTMLSelectElement)
                            .value as RuntimeMode,
                    )}
            >
                <option value={DEFAULT_RUNTIME_MODE}
                    >runtime_compatibility_mode</option
                >
                <option value={VNEXT_SPEC_MODE}>vnext_spec_mode</option>
            </select>
            {#if errors.runtime}<small>{errors.runtime}</small>{/if}
        </label>
        <label>
            <span>Default Bundle</span>
            <select
                value={form.defaultBundleVersion ?? ""}
                disabled={!runtimeUsesDefaults()}
                onchange={(event) =>
                    (form.defaultBundleVersion = ((
                        event.currentTarget as HTMLSelectElement
                    ).value || null) as typeof form.defaultBundleVersion)}
            >
                <option value="">None</option>
                <option value={DEFAULT_BUNDLE_VERSION}>research_spec_v1</option>
            </select>
        </label>
        <label>
            <span>Return Target</span>
            <select bind:value={form.returnTarget}>
                <option value="open_to_open">open_to_open</option>
                <option value="close_to_close">close_to_close</option>
                <option value="open_to_close">open_to_close</option>
            </select>
        </label>
    </div>

    <div class="group four">
        <label>
            <span>Start Date</span>
            <input type="date" bind:value={form.startDate} />
        </label>
        <label>
            <span>End Date</span>
            <input type="date" bind:value={form.endDate} />
        </label>
        <label>
            <span>Horizon Days</span>
            <input type="number" min="1" bind:value={form.horizonDays} />
            {#if errors.horizonDays}<small>{errors.horizonDays}</small>{/if}
        </label>
        <label class="toggle">
            <span>Allow Proactive Sells</span>
            <input type="checkbox" bind:checked={form.allowProactiveSells} />
        </label>
    </div>
    {#if errors.dateRange}<small>{errors.dateRange}</small>{/if}

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Strategy</p>
                <h4>Threshold and Selection</h4>
            </div>
        </div>
        <div class="group three">
            <label>
                <span>Threshold</span>
                <input type="number" step="0.001" bind:value={form.threshold} />
                {#if errors.threshold}<small>{errors.threshold}</small>{/if}
            </label>
            <label>
                <span>Top N</span>
                <input type="number" min="1" bind:value={form.topN} />
                {#if errors.topN}<small>{errors.topN}</small>{/if}
            </label>
            <label>
                <span>Validation Enabled</span>
                <input type="checkbox" bind:checked={form.enableValidation} />
            </label>
        </div>
    </div>

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Features</p>
                <h4>Signal Inputs</h4>
            </div>
            <button type="button" class="secondary" onclick={addFeature}
                >Add Feature</button
            >
        </div>
        <div class="feature-list">
            {#each form.features as feature}
                <div class="feature-row">
                    <label>
                        <span>Name</span>
                        <select
                            value={feature.name}
                            onchange={(event) =>
                                updateFeature(
                                    feature.id,
                                    "name",
                                    (event.currentTarget as HTMLSelectElement)
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
                                updateFeature(
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
                                updateFeature(
                                    feature.id,
                                    "source",
                                    (event.currentTarget as HTMLSelectElement)
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
                                updateFeature(
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
                        onclick={() => removeFeature(feature.id)}>Remove</button
                    >
                    {#if errors[`feature-${feature.id}`]}
                        <small class="full"
                            >{errors[`feature-${feature.id}`]}</small
                        >
                    {/if}
                </div>
            {/each}
        </div>
    </div>

    <div class="group three">
        <label>
            <span>Slippage</span>
            <input
                type="number"
                min="0"
                step="0.001"
                bind:value={form.slippage}
            />
        </label>
        <label>
            <span>Fees</span>
            <input type="number" min="0" step="0.001" bind:value={form.fees} />
        </label>
        <label>
            <span>Portfolio AUM</span>
            <input
                type="number"
                min="0"
                step="100000"
                bind:value={form.portfolioAum}
                placeholder="Optional"
            />
            {#if errors.portfolioAum}<small>{errors.portfolioAum}</small>{/if}
        </label>
    </div>

    <div class="group two">
        <label class="toggle">
            <span>Record As P3 Monitor Run</span>
            <input type="checkbox" bind:checked={form.recordAsMonitorRun} />
        </label>
        <label>
            <span>Baselines</span>
            <div class="baseline-list">
                {#each availableBaselines as baseline}
                    <label class="checkbox">
                        <input
                            type="checkbox"
                            checked={form.baselines.includes(baseline)}
                            onchange={() => toggleBaseline(baseline)}
                        />
                        <span>{baseline}</span>
                    </label>
                {/each}
            </div>
        </label>
    </div>
    {#if errors.execution}<small>{errors.execution}</small>{/if}

    {#if form.enableValidation}
        <div class="group three">
            <label>
                <span>Validation Method</span>
                <select bind:value={form.validationMethod}>
                    <option value="holdout">holdout</option>
                    <option value="walk_forward">walk_forward</option>
                    <option value="rolling_window">rolling_window</option>
                    <option value="expanding_window">expanding_window</option>
                </select>
            </label>
            <label>
                <span>Splits</span>
                <input
                    type="number"
                    min="1"
                    bind:value={form.validationSplits}
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
                    bind:value={form.validationTestSize}
                />
                {#if errors.validationTestSize}<small
                        >{errors.validationTestSize}</small
                    >{/if}
            </label>
        </div>
    {/if}

    <button
        type="button"
        class="submit"
        onclick={submitForm}
        disabled={isSubmitting}
    >
        {isSubmitting ? "Running Research Run..." : "Create Research Run"}
    </button>
</div>

<style>
    .panel,
    .surface,
    .feature-list,
    .feature-row,
    .group,
    .baseline-list {
        display: grid;
        gap: 0.9rem;
    }

    .panel,
    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }

    .section-header,
    .surface-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
    }

    .eyebrow {
        margin: 0 0 0.3rem;
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    h3,
    h4 {
        margin: 0;
    }

    .group.two {
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
    button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }

    .baseline-list {
        grid-template-columns: 1fr;
        padding-top: 0.35rem;
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
    }

    button {
        cursor: pointer;
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

    small {
        color: #fca5a5;
    }

    @media (max-width: 1100px) {
        .group.two,
        .group.three,
        .group.four,
        .feature-row {
            grid-template-columns: 1fr;
        }
    }
</style>
