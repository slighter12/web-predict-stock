<script lang="ts">
    import { onMount } from "svelte";

    import { ApiError, fetchResearchGate } from "../api";
    import { buildCapabilityReadinessMap } from "../state/researchWorkflow";
    import type {
        ResearchPhaseGateResponse,
        ResearchRunResponse,
        ResearchSubmissionSummary,
    } from "../types";
    import OperationsWorkspace from "./OperationsWorkspace.svelte";
    import ResearchWorkspace from "./ResearchWorkspace.svelte";
    import RunReviewWorkspace from "./RunReviewWorkspace.svelte";

    type SurfaceId = "start" | "builder" | "experiments" | "data_ops";

    let activeSurface: SurfaceId = "start";
    let latestResult: ResearchRunResponse | null = null;
    let latestSubmission: ResearchSubmissionSummary | null = null;

    const gatePhases = ["p7", "p8", "p9", "p10", "p11"] as const;
    let gates: ResearchPhaseGateResponse[] = [];
    let gateLoadError: string | null = null;

    const loadGateReadiness = async () => {
        const nextGates: ResearchPhaseGateResponse[] = [];
        const failures: string[] = [];

        for (const phase of gatePhases) {
            try {
                nextGates.push(await fetchResearchGate(phase));
            } catch (error) {
                failures.push(
                    error instanceof ApiError
                        ? `${phase.toUpperCase()}: ${error.code}`
                        : `${phase.toUpperCase()}: unavailable`,
                );
            }
        }

        gates = nextGates;
        gateLoadError = failures.length ? failures.join(" / ") : null;
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
        void loadGateReadiness();
    });

    $: capabilityReadiness = buildCapabilityReadinessMap(gates);
    $: readinessCounts = Object.values(capabilityReadiness).reduce(
        (summary, readiness) => {
            summary[readiness.status] += 1;
            return summary;
        },
        {
            available: 0,
            setup_required: 0,
            gated: 0,
            not_implemented: 0,
        },
    );
</script>

<div class="dashboard-shell">
    <section class="surface shell-hero">
        <div class="shell-hero__copy">
            <p class="eyebrow">TW Daily Quant ML Research Workbench</p>
            <h2>
                Start with a baseline experiment, inspect model quality, then
                compare persisted research runs.
            </h2>
            <p class="muted">
                The default path is Dataset, Features, Prediction Task, Model
                Diagnostics, Strategy Backtest, and Experiment Comparison.
            </p>
        </div>

        <div class="shell-hero__meta">
            <div class="meta-card">
                <span>V1 Focus</span>
                <strong>TW daily baseline study</strong>
                <p>Regression diagnostics first, strategy metrics second.</p>
            </div>
            <div class="meta-card">
                <span>Artifacts</span>
                <strong>Persisted review</strong>
                <p>Config, diagnostics, signals, equity, baselines, warnings.</p>
            </div>
            <div class="meta-card">
                <span>Advanced</span>
                <strong>Hidden by default</strong>
                <p>Execution, adaptive, peer, factor, and tick archive modules.</p>
            </div>
        </div>
    </section>

    {#if activeSurface === "start"}
        <section class="surface task-entry">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Start</p>
                    <h3>Choose the next research task</h3>
                </div>
            </div>

            <div class="task-grid">
                <button
                    type="button"
                    class="task-card"
                    onclick={() => setSurface("builder")}
                >
                    <span>Start Baseline Study</span>
                    <strong>Open the experiment builder</strong>
                    <p>TW daily dataset, features, model, validation, review.</p>
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
                    <p>Review diagnostics, artifacts, and comparison context.</p>
                </button>
                <button
                    type="button"
                    class="task-card"
                    onclick={() => setSurface("data_ops")}
                >
                    <span>Check Data Readiness</span>
                    <strong>{readinessCounts.available} readiness checks available</strong>
                    <p>Use data diagnostics only when research inputs need inspection.</p>
                </button>
            </div>
        </section>
    {/if}

    <section class="surface shell-nav">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Navigation</p>
                <h3>Workbench surfaces</h3>
            </div>
            <div class="readiness-strip">
                <span>{readinessCounts.available} available</span>
                <span>{readinessCounts.setup_required} setup required</span>
                <span>{readinessCounts.gated} gated</span>
                {#if gateLoadError}
                    <span class="readiness-strip__warning">{gateLoadError}</span
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
                <strong>Task entry for the baseline research loop</strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface === "builder"}
                onclick={() => setSurface("builder")}
            >
                <span>Experiment Builder</span>
                <strong>Dataset, features, prediction task, validation</strong>
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
                        ? `Latest run ${latestResult.run_id} is ready to review`
                        : "Load, inspect, and compare persisted runs"}
                </strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface ===
                    "data_ops"}
                onclick={() => setSurface("data_ops")}
            >
                <span>Data Ops</span>
                <strong>Secondary diagnostics for data readiness</strong>
            </button>
        </div>
    </section>

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
    .shell-hero__meta,
    .surface-nav,
    .task-grid {
        display: grid;
        gap: var(--space-4);
    }

    .shell-hero {
        grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.9fr);
        align-items: stretch;
        gap: var(--space-5);
        background:
            linear-gradient(
                135deg,
                rgba(10, 31, 44, 0.96),
                rgba(8, 20, 34, 0.94)
            ),
            var(--surface-1);
    }

    .shell-hero__copy {
        display: grid;
        gap: var(--space-3);
        align-content: start;
    }

    h2,
    h3,
    p {
        margin: 0;
    }

    h2 {
        font-size: clamp(2rem, 4vw, 3.3rem);
        line-height: 1.05;
        letter-spacing: 0;
    }

    .shell-hero__meta {
        grid-template-columns: 1fr;
    }

    .meta-card,
    .surface-nav__button {
        display: grid;
        gap: 0.45rem;
        text-align: left;
        padding: 1rem 1.05rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(6, 18, 30, 0.84);
    }

    .meta-card span,
    .surface-nav__button span {
        color: var(--accent-primary);
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .meta-card p,
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

    .task-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
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
        .shell-hero,
        .surface-nav,
        .task-grid {
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
