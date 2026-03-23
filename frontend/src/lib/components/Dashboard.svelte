<script lang="ts">
    import { onMount } from "svelte";

    import PredictionStudio from "./PredictionStudio.svelte";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";

    type SvelteModule = {
        default: new (...args: never[]) => unknown;
    };

    let maintenanceWorkspacePromise: Promise<SvelteModule> | null = null;
    let maintenanceLoadError: string | null = null;

    const commandDeck = [
        {
            href: "#prediction-studio",
            label: "Prediction Studio",
            detail: "Build the feature, model, validation, and result flow in one surface.",
        },
        {
            href: "#maintenance-workspace",
            label: "Maintenance",
            detail: "Open repair, replay, event correction, and execution diagnostics only when the workflow needs intervention.",
        },
    ];

    function loadMaintenanceWorkspace() {
        if (maintenanceWorkspacePromise) {
            return;
        }

        maintenanceLoadError = null;
        maintenanceWorkspacePromise =
            import("./MaintenanceWorkspace.svelte").catch((error) => {
                maintenanceLoadError =
                    error instanceof Error
                        ? error.message
                        : "Unable to load maintenance workspace.";
                maintenanceWorkspacePromise = null;
                throw error;
            });
    }

    onMount(() => {
        let isDisposed = false;

        const queueLoad = () => {
            if (!isDisposed) {
                loadMaintenanceWorkspace();
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
        <h2>
            Prediction first. Maintenance only when the workflow needs repair.
        </h2>
        <p class="command-shell__summary">
            Start with Prediction Studio to build the feature and model flow.
            Open Maintenance only for replay, recovery, event correction, or
            execution diagnostics.
        </p>
    </div>

    <div class="command-shell__callout">
        Prediction Studio is the primary path. Maintenance stays available for
        repair and diagnostics, but it no longer competes with the modeling
        flow.
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
    <PredictionStudio />

    {#if maintenanceWorkspacePromise}
        {#await maintenanceWorkspacePromise}
            <WorkspaceSection
                id="maintenance-workspace"
                eyebrow="Maintenance"
                title="Maintenance"
                description="Loading replay, repair, and diagnostics tools."
            >
                <div class="workspace-placeholder">
                    Loading maintenance workspace...
                </div>
            </WorkspaceSection>
        {:then maintenanceWorkspaceModule}
            <svelte:component this={maintenanceWorkspaceModule.default} />
        {:catch}
            <WorkspaceSection
                id="maintenance-workspace"
                eyebrow="Maintenance"
                title="Maintenance"
                description="Replay, repair, and diagnostics tools stay outside the primary prediction flow."
            >
                <p class="workspace-error">
                    {maintenanceLoadError ??
                        "Unable to load maintenance workspace."}
                </p>
            </WorkspaceSection>
        {/await}
    {:else}
        <WorkspaceSection
            id="maintenance-workspace"
            eyebrow="Maintenance"
            title="Maintenance"
            description="Replay, repair, and diagnostics tools stay outside the primary prediction flow."
        >
            <div class="workspace-placeholder">
                Preparing maintenance workspace...
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

    .command-shell__callout {
        max-width: 70ch;
        padding: 0.95rem 1rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(125, 211, 252, 0.08);
        background: rgba(10, 24, 39, 0.72);
        color: var(--text-secondary);
    }

    .workspace-nav {
        display: grid;
        gap: 1rem;
        grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
    }

    .workspace-nav__link {
        display: grid;
        gap: 0.45rem;
        padding: 1rem 1.1rem;
        border-radius: 18px;
        border: 1px solid rgba(125, 211, 252, 0.14);
        background: rgba(5, 13, 22, 0.72);
        color: inherit;
        text-decoration: none;
        transition:
            transform 140ms ease,
            border-color 140ms ease;
    }

    .workspace-nav__link span {
        color: var(--muted);
        font-size: 0.74rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .workspace-nav__link strong {
        font-size: 0.98rem;
        line-height: 1.45;
        font-weight: 600;
    }

    .workspace-nav__link:hover {
        transform: translateY(-1px);
        border-color: rgba(245, 158, 11, 0.34);
    }

    .dashboard-grid {
        display: grid;
        gap: 1.4rem;
    }

    .workspace-placeholder,
    .workspace-error {
        padding: 0.95rem 1rem;
        border-radius: 16px;
        background: rgba(2, 6, 23, 0.42);
        color: var(--muted);
    }

    @media (max-width: 960px) {
        .command-shell__stats,
        .workspace-nav {
            grid-template-columns: 1fr;
        }
    }
</style>
