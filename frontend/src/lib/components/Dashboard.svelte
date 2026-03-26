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

    type SurfaceId = "research" | "review" | "operations";

    let activeSurface: SurfaceId = "research";
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
        activeSurface = "review";
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
            <p class="eyebrow">Research Workbench V2</p>
            <h2>
                Build research first, review it as a decision, and only open
                operations when the data plane actually needs repair.
            </h2>
            <p class="muted">
                The new shell separates research workflow, run review, and
                operations so ML expansion no longer has to live inside a single
                overloaded page.
            </p>
        </div>

        <div class="shell-hero__meta">
            <div class="meta-card">
                <span>Research</span>
                <strong>Primary path</strong>
                <p>
                    Templates, capabilities, model family selection, and run
                    submission.
                </p>
            </div>
            <div class="meta-card">
                <span>Run Review</span>
                <strong>Decision view</strong>
                <p>
                    Outcome, baseline verdict, comparison eligibility, and
                    governance context.
                </p>
            </div>
            <div class="meta-card">
                <span>Operations</span>
                <strong>Secondary path</strong>
                <p>
                    Repair, replay, tick archive, lifecycle correction, and
                    event fixes.
                </p>
            </div>
        </div>
    </section>

    <section class="surface shell-nav">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Navigation</p>
                <h3>Choose the surface you want</h3>
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
                class:surface-nav__button--active={activeSurface === "research"}
                onclick={() => setSurface("research")}
            >
                <span>Research</span>
                <strong>Start from a template and run a workflow</strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface === "review"}
                onclick={() => setSurface("review")}
            >
                <span>Run Review</span>
                <strong>
                    {latestResult
                        ? `Latest run ${latestResult.run_id} is ready to review`
                        : "Review the latest result or load a persisted run"}
                </strong>
            </button>
            <button
                type="button"
                class:surface-nav__button={true}
                class:surface-nav__button--active={activeSurface ===
                    "operations"}
                onclick={() => setSurface("operations")}
            >
                <span>Operations</span>
                <strong
                    >Repair, replay, archive, and market-state correction</strong
                >
            </button>
        </div>
    </section>

    {#if activeSurface === "research"}
        <ResearchWorkspace
            {capabilityReadiness}
            on:runcreated={handleRunCreated}
        />
    {/if}

    {#if activeSurface === "review"}
        <RunReviewWorkspace
            {capabilityReadiness}
            {latestResult}
            {latestSubmission}
        />
    {/if}

    {#if activeSurface === "operations"}
        <OperationsWorkspace />
    {/if}
</div>

<style lang="scss">
    .dashboard-shell,
    .shell-hero__meta,
    .surface-nav {
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
        letter-spacing: -0.04em;
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
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .surface-nav__button--active {
        border-color: rgba(56, 189, 248, 0.38);
        background: rgba(9, 32, 49, 0.94);
        box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.14);
    }

    @media (max-width: 1100px) {
        .shell-hero,
        .surface-nav {
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
