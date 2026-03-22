<script lang="ts">
    import { onMount } from "svelte";

    import WorkspaceSection from "./layout/WorkspaceSection.svelte";

    type SvelteModule = {
        default: new (...args: never[]) => unknown;
    };

    const researchWorkspacePromise = import("./ResearchWorkspace.svelte");
    let dataPlaneWorkspacePromise: Promise<SvelteModule> | null = null;
    let dataPlaneLoadError: string | null = null;

    const commandDeck = [
        {
            href: "#research-workspace",
            label: "Research Workspace",
            detail: "Configure runs, inspect saved records, and review metrics, validation, and comparisons.",
        },
        {
            href: "#data-plane-workspace",
            label: "Operations Workspace",
            detail: "Manage ingestion, replay, lifecycle, execution control, and recovery tools.",
        },
    ];

    const terminalStats = [
        {
            label: "Research Flow",
            detail: "Configure runs, inspect saved records, and review performance in one continuous workflow.",
        },
        {
            label: "Operations Flow",
            detail: "Handle ingestion, replay, lifecycle, and execution support from a shared control area.",
        },
        {
            label: "Readiness Flow",
            detail: "Review data, execution, and adaptive readiness without exposing internal gate codes.",
        },
    ];

    function loadDataPlaneWorkspace() {
        if (dataPlaneWorkspacePromise) {
            return;
        }

        dataPlaneLoadError = null;
        dataPlaneWorkspacePromise = import("./DataPlaneWorkspace.svelte").catch(
            (error) => {
                dataPlaneLoadError =
                    error instanceof Error
                        ? error.message
                        : "Unable to load data plane workspace.";
                dataPlaneWorkspacePromise = null;
                throw error;
            },
        );
    }

    onMount(() => {
        let isDisposed = false;

        const queueLoad = () => {
            if (!isDisposed) {
                loadDataPlaneWorkspace();
            }
        };

        if (typeof window.requestIdleCallback === "function") {
            const handle = window.requestIdleCallback(queueLoad, {
                timeout: 500,
            });

            return () => {
                isDisposed = true;
                window.cancelIdleCallback(handle);
            };
        }

        const timeoutId = window.setTimeout(queueLoad, 180);

        return () => {
            isDisposed = true;
            window.clearTimeout(timeoutId);
        };
    });
</script>

<section class="command-shell">
    <div class="command-shell__intro">
        <p class="eyebrow">Workspace Overview</p>
        <h2>Research and operations share one clear workspace.</h2>
        <p class="command-shell__summary">
            Use the research side to configure and review runs. Use the
            operations side to manage data refreshes and execution support
            tasks.
        </p>
    </div>

    <div class="command-shell__stats">
        {#each terminalStats as stat}
            <article class="stat-card">
                <span>{stat.label}</span>
                <p>{stat.detail}</p>
            </article>
        {/each}
    </div>

    <nav class="workspace-nav" aria-label="Workspace navigation">
        {#each commandDeck as item}
            <a href={item.href} class="workspace-nav__link">
                <span>{item.label}</span>
                <strong>{item.detail}</strong>
            </a>
        {/each}
    </nav>
</section>

<div class="dashboard-grid">
    {#await researchWorkspacePromise}
        <WorkspaceSection
            id="research-workspace"
            eyebrow="Research Runs"
            title="Research Workspace"
            description="Configure runs, inspect saved records, and review performance, validation, and comparison data."
        >
            <div class="workspace-placeholder">
                Loading research workspace...
            </div>
        </WorkspaceSection>
    {:then researchWorkspaceModule}
        <svelte:component this={researchWorkspaceModule.default} />
    {:catch error}
        <WorkspaceSection
            id="research-workspace"
            eyebrow="Research Runs"
            title="Research Workspace"
            description="Configure runs, inspect saved records, and review performance, validation, and comparison data."
        >
            <p class="workspace-error">
                {error instanceof Error
                    ? error.message
                    : "Unable to load research workspace."}
            </p>
        </WorkspaceSection>
    {/await}

    {#if dataPlaneWorkspacePromise}
        {#await dataPlaneWorkspacePromise}
            <WorkspaceSection
                id="data-plane-workspace"
                eyebrow="Data Plane"
                title="Operations Workspace"
                description="Manage ingestion, lifecycle, replay, adaptive control, and execution support from one view."
            >
                <div class="workspace-placeholder">
                    Loading data plane workspace...
                </div>
            </WorkspaceSection>
        {:then dataPlaneWorkspaceModule}
            <svelte:component this={dataPlaneWorkspaceModule.default} />
        {:catch}
            <WorkspaceSection
                id="data-plane-workspace"
                eyebrow="Data Plane"
                title="Operations Workspace"
                description="Manage ingestion, lifecycle, replay, adaptive control, and execution support from one view."
            >
                <p class="workspace-error">
                    {dataPlaneLoadError ??
                        "Unable to load data plane workspace."}
                </p>
            </WorkspaceSection>
        {/await}
    {:else}
        <WorkspaceSection
            id="data-plane-workspace"
            eyebrow="Data Plane"
            title="Operations Workspace"
            description="Manage ingestion, lifecycle, replay, adaptive control, and execution support from one view."
        >
            <div class="workspace-placeholder">
                Preparing data plane workspace...
            </div>
        </WorkspaceSection>
    {/if}
</div>

<style lang="scss">
    .command-shell {
        display: grid;
        gap: 1rem;
        padding: 1.2rem;
        border-radius: var(--radius-xl);
        border: 1px solid var(--border-subtle);
        background:
            linear-gradient(
                180deg,
                rgba(8, 21, 35, 0.92),
                rgba(5, 13, 22, 0.88)
            ),
            var(--surface-raised);
        box-shadow: var(--shadow-soft);
    }

    .command-shell__intro {
        display: grid;
        gap: 0.45rem;
        max-width: 70ch;
    }

    h2 {
        margin: 0;
        font-size: clamp(1.8rem, 3vw, 2.6rem);
        line-height: 1.02;
        letter-spacing: -0.04em;
    }

    .command-shell__summary {
        margin: 0;
        color: var(--text-secondary);
    }

    .command-shell__stats {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .stat-card {
        display: grid;
        gap: 0.45rem;
        padding: 1rem;
        align-content: start;
        border-radius: var(--radius-md);
        border: 1px solid rgba(125, 211, 252, 0.08);
        background: rgba(10, 24, 39, 0.72);
    }

    .stat-card span {
        color: var(--muted);
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .stat-card p {
        margin: 0;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    .workspace-nav {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .workspace-nav__link {
        display: grid;
        gap: 0.4rem;
        padding: 1rem 1.05rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(125, 211, 252, 0.14);
        background: rgba(13, 31, 49, 0.66);
        transition:
            transform var(--motion-fast),
            border-color var(--motion-fast),
            background var(--motion-fast);
    }

    .workspace-nav__link span {
        color: var(--accent-primary);
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }

    .workspace-nav__link strong {
        color: var(--text-secondary);
        font-size: 0.94rem;
        line-height: 1.45;
        font-weight: 500;
    }

    .workspace-nav__link:hover {
        transform: translateY(-1px);
        border-color: rgba(125, 211, 252, 0.28);
        background: rgba(15, 35, 54, 0.84);
    }

    .dashboard-grid {
        display: grid;
        gap: 1.4rem;
    }

    @media (max-width: 960px) {
        .command-shell__stats,
        .workspace-nav {
            grid-template-columns: 1fr;
        }
    }
</style>
