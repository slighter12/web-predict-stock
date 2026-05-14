<script lang="ts">
    import { onMount } from "svelte";

    import { ApiError, fetchTwDailyReadiness } from "../api";
    import {
        buildCapabilityReadinessMap,
        createDefaultResearchWorkflowDraft,
        parseSymbols,
    } from "../state/researchWorkflow";
    import type {
        ResearchRunResponse,
        ResearchSubmissionSummary,
        TwDailyReadinessResponse,
    } from "../types";
    import OperationsWorkspace from "./OperationsWorkspace.svelte";
    import ResearchWorkspace from "./ResearchWorkspace.svelte";
    import RunReviewWorkspace from "./RunReviewWorkspace.svelte";

    type SurfaceId = "start" | "builder" | "experiments" | "data_ops";

    let activeSurface: SurfaceId = "start";
    let latestResult: ResearchRunResponse | null = null;
    let latestSubmission: ResearchSubmissionSummary | null = null;
    const builderDefaults = createDefaultResearchWorkflowDraft();
    let readinessSymbolsInput = builderDefaults.universe.symbolsInput;
    let readinessStartDate = builderDefaults.universe.startDate;
    let readinessEndDate = builderDefaults.universe.endDate;
    let readinessData: TwDailyReadinessResponse | null = null;
    let readinessLoadError: string | null = null;

    const loadTwDailyReadiness = async () => {
        const symbols = parseSymbols(readinessSymbolsInput);
        if (!symbols.length) {
            readinessLoadError = "Enter at least one symbol to check readiness.";
            readinessData = null;
            return;
        }
        try {
            readinessData = await fetchTwDailyReadiness({
                market: "TW",
                symbols,
                date_range:
                    readinessStartDate && readinessEndDate
                        ? {
                              start: readinessStartDate,
                              end: readinessEndDate,
                          }
                        : undefined,
            });
            readinessLoadError = null;
        } catch (error) {
            readinessLoadError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "TW daily readiness is unavailable.";
        }
    };

    const setSurface = (surfaceId: SurfaceId) => {
        activeSurface = surfaceId;
    };

    const handleRunCreated = (
        event: CustomEvent<{
            result: ResearchRunResponse;
            summary: ResearchSubmissionSummary;
        }>,
    ) => {
        latestResult = event.detail.result;
        latestSubmission = event.detail.summary;
        activeSurface = "experiments";
    };

    onMount(() => {
        void loadTwDailyReadiness();
    });

    $: capabilityReadiness = buildCapabilityReadinessMap();
    $: readinessCounts = readinessData?.summary ?? {
        ready: 0,
        warning: 0,
        missing: 0,
        stale: 0,
    };
</script>

<div class="dashboard-shell">
    {#if activeSurface === "start"}
        <section class="surface task-entry">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">TW Daily Quant ML Research Workbench</p>
                    <h2>What do you want to do next?</h2>
                </div>
                <p class="muted">
                    Start a baseline run, review a saved run, or check whether
                    the requested TW daily data is ready.
                </p>
            </div>

            <div class="task-grid">
                <button
                    type="button"
                    class="task-card"
                    onclick={() => setSurface("builder")}
                >
                    <span>Start Baseline Study</span>
                    <strong>Build and run a TW daily experiment</strong>
                    <p>Dataset, features, model, validation, and review.</p>
                </button>
                <button
                    type="button"
                    class="task-card"
                    onclick={() => setSurface("experiments")}
                >
                    <span>Open Recent Experiment</span>
                    <strong>
                        {latestResult
                            ? `Latest: ${latestResult.run_id}`
                            : "Load from persisted runs"}
                    </strong>
                    <p>Reload a saved result, inspect it, then compare.</p>
                </button>
                <button
                    type="button"
                    class="task-card"
                    onclick={() => setSurface("data_ops")}
                >
                    <span>Check Data Readiness</span>
                    <strong>{readinessCounts.ready} ready symbols</strong>
                    <p>Troubleshoot warning or missing symbols before a run.</p>
                </button>
            </div>

            <details class="readiness-support">
                <summary>
                    Data readiness support:
                    {readinessCounts.ready} ready,
                    {readinessCounts.warning} warning,
                    {readinessCounts.missing + readinessCounts.stale}
                    missing or stale
                </summary>

                <div class="readiness-controls">
                    <label>
                        <span>Requested Symbols</span>
                        <input
                            bind:value={readinessSymbolsInput}
                            placeholder="2330, 2317"
                        />
                    </label>
                    <label>
                        <span>Start Date</span>
                        <input type="date" bind:value={readinessStartDate} />
                    </label>
                    <label>
                        <span>End Date</span>
                        <input type="date" bind:value={readinessEndDate} />
                    </label>
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => void loadTwDailyReadiness()}
                    >
                        Refresh
                    </button>
                </div>
                {#if readinessLoadError}
                    <p class="muted readiness-message">{readinessLoadError}</p>
                {/if}
                {#if readinessData?.symbols.length}
                    <div
                        class="readiness-details"
                        aria-label="TW daily readiness details"
                    >
                        {#each readinessData.symbols.slice(0, 4) as symbol}
                            <article
                                class={`readiness-row readiness-row--${symbol.status}`}
                            >
                                <div>
                                    <strong>{symbol.symbol}</strong>
                                    <span>{symbol.status}</span>
                                </div>
                                <p>
                                    {#if symbol.warnings.length}
                                        {symbol.warnings[0]}
                                    {:else}
                                        Latest daily row: {symbol.latest_daily_date ?? "unavailable"}
                                    {/if}
                                </p>
                            </article>
                        {/each}
                    </div>
                {/if}
            </details>

            <div class="workflow-strip" aria-label="Core workflow">
                <span>Start</span>
                <span>Builder</span>
                <span>Run</span>
                <span>Review</span>
                <span>Reload</span>
                <span>Compare</span>
            </div>
        </section>
    {/if}

    {#if activeSurface !== "start"}
        <section class="surface shell-nav">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Navigation</p>
                <h3>Research workflow</h3>
            </div>
            <div class="readiness-strip">
                <span>{readinessCounts.ready} ready</span>
                <span>{readinessCounts.warning} warning</span>
                <span>{readinessCounts.missing + readinessCounts.stale} missing/stale</span>
                {#if readinessLoadError}
                    <span class="readiness-strip__warning">{readinessLoadError}</span
                    >
                {/if}
            </div>
        </div>

        <div class="surface-nav">
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface === "start"}
                onclick={() => setSurface("start")}
            >
                <span>Start</span>
                <strong>Choose the next task</strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface === "builder"}
                onclick={() => setSurface("builder")}
            >
                <span>Experiment Builder</span>
                <strong>Dataset, features, model, validation</strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface ===
                    "experiments"}
                onclick={() => setSurface("experiments")}
            >
                <span>Experiments</span>
                <strong>
                    {latestResult
                        ? `Latest run ${latestResult.run_id} is ready`
                        : "Reload, inspect, and compare runs"}
                </strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface ===
                    "data_ops"}
                onclick={() => setSurface("data_ops")}
            >
                <span>Data Readiness</span>
                <strong>Support checks for requested TW symbols</strong>
            </button>
        </div>
        </section>
    {/if}

    {#if activeSurface === "builder"}
        <ResearchWorkspace
            {capabilityReadiness}
            on:runcreated={handleRunCreated}
        />
    {/if}

    {#if activeSurface === "experiments"}
        <RunReviewWorkspace
            {capabilityReadiness}
            {latestResult}
            {latestSubmission}
        />
    {/if}

    {#if activeSurface === "data_ops"}
        <OperationsWorkspace />
    {/if}
</div>

<style lang="scss">
    .dashboard-shell,
    .surface-nav,
    .task-grid {
        display: grid;
        gap: var(--space-4);
    }

    h2,
    h3,
    p {
        margin: 0;
    }

    h2 {
        font-size: clamp(1.7rem, 3vw, 2.55rem);
        line-height: 1.08;
        letter-spacing: 0;
    }

    .surface-nav__button {
        display: grid;
        gap: 0.45rem;
        text-align: left;
        padding: 1rem 1.05rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(6, 18, 30, 0.84);
    }

    .surface-nav__button span {
        color: var(--accent-primary);
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .surface-nav__button strong {
        color: var(--text-secondary);
        line-height: 1.45;
    }

    .shell-nav {
        gap: var(--space-4);
    }

    .task-entry {
        gap: var(--space-4);
    }

    .readiness-support {
        display: grid;
        gap: var(--space-3);
        padding: 0.95rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(6, 18, 30, 0.58);
    }

    .readiness-support summary {
        cursor: pointer;
        color: var(--text-secondary);
        font-weight: 600;
    }

    .readiness-support[open] summary {
        margin-bottom: var(--space-3);
    }

    .workflow-strip {
        display: flex;
        gap: 0.55rem;
        flex-wrap: wrap;
    }

    .workflow-strip span {
        display: inline-flex;
        align-items: center;
        min-height: 2rem;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 35, 54, 0.72);
        color: var(--muted);
        font-size: 0.8rem;
    }

    .task-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .readiness-controls {
        display: grid;
        gap: var(--space-3);
        grid-template-columns: minmax(0, 1.4fr) repeat(2, minmax(0, 1fr)) auto;
        align-items: end;
    }

    .readiness-controls label {
        display: grid;
        gap: 0.35rem;
    }

    .readiness-controls span {
        color: var(--muted);
        font-size: 0.78rem;
    }

    .readiness-message {
        margin: 0;
    }

    .readiness-details {
        display: grid;
        gap: var(--space-2);
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .readiness-row {
        display: grid;
        gap: 0.5rem;
        padding: 0.8rem 0.9rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(6, 18, 30, 0.78);
    }

    .readiness-row div {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2);
    }

    .readiness-row strong {
        color: var(--text-primary);
    }

    .readiness-row span {
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }

    .readiness-row p {
        color: var(--muted);
        line-height: 1.45;
    }

    .readiness-row--warning {
        border-color: rgba(245, 158, 11, 0.28);
    }

    .readiness-row--missing {
        border-color: rgba(248, 113, 113, 0.32);
    }

    .readiness-strip {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .readiness-strip span {
        display: inline-flex;
        align-items: center;
        min-height: 2rem;
        padding: 0.2rem 0.75rem;
        border-radius: 999px;
        background: rgba(6, 18, 30, 0.84);
        color: var(--muted);
        font-size: 0.8rem;
    }

    .readiness-strip__warning {
        border: 1px solid rgba(245, 158, 11, 0.24);
        background: rgba(120, 53, 15, 0.22);
        color: var(--warning);
    }

    .surface-nav {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .task-card {
        display: grid;
        gap: 0.55rem;
        min-height: 8rem;
        text-align: left;
        padding: 1.05rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(6, 18, 30, 0.9);
    }

    .task-card span {
        color: var(--accent-primary);
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .task-card p {
        color: var(--muted);
        line-height: 1.45;
    }

    .surface-nav__button--active {
        border-color: rgba(56, 189, 248, 0.38);
        background: rgba(9, 32, 49, 0.94);
        box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.14);
    }

    @media (max-width: 1100px) {
        .surface-nav,
        .task-grid,
        .readiness-details,
        .readiness-controls {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 720px) {
        .readiness-strip {
            align-items: flex-start;
            flex-direction: column;
        }
    }
</style>
