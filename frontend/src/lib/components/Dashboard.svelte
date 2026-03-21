<script lang="ts">
    import { onMount } from "svelte";

    import WorkspaceSection from "./layout/WorkspaceSection.svelte";

    type SvelteModule = {
        default: new (...args: never[]) => unknown;
    };

    const researchWorkspacePromise = import("./ResearchWorkspace.svelte");
    let dataPlaneWorkspacePromise: Promise<SvelteModule> | null = null;
    let dataPlaneLoadError: string | null = null;

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

<div class="dashboard-grid">
    {#await researchWorkspacePromise}
        <WorkspaceSection
            eyebrow="Research Runs"
            title="Research Run Workspace"
        >
            <div class="workspace-placeholder">
                Loading research workspace...
            </div>
        </WorkspaceSection>
    {:then researchWorkspaceModule}
        <svelte:component this={researchWorkspaceModule.default} />
    {:catch error}
        <WorkspaceSection
            eyebrow="Research Runs"
            title="Research Run Workspace"
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
            <WorkspaceSection eyebrow="Data Plane" title="Data Plane Workspace">
                <div class="workspace-placeholder">
                    Loading data plane workspace...
                </div>
            </WorkspaceSection>
        {:then dataPlaneWorkspaceModule}
            <svelte:component this={dataPlaneWorkspaceModule.default} />
        {:catch}
            <WorkspaceSection eyebrow="Data Plane" title="Data Plane Workspace">
                <p class="workspace-error">
                    {dataPlaneLoadError ??
                        "Unable to load data plane workspace."}
                </p>
            </WorkspaceSection>
        {/await}
    {:else}
        <WorkspaceSection eyebrow="Data Plane" title="Data Plane Workspace">
            <div class="workspace-placeholder">
                Preparing data plane workspace...
            </div>
        </WorkspaceSection>
    {/if}
</div>

<style>
    .dashboard-grid {
        display: grid;
        gap: 1.2rem;
    }

    .workspace-placeholder,
    .workspace-error {
        min-height: 5.5rem;
        display: grid;
        place-items: center;
        margin: 0;
        border-radius: 18px;
        border: 1px dashed rgba(148, 163, 184, 0.22);
        background: rgba(15, 23, 42, 0.2);
        color: var(--muted);
        text-align: center;
        padding: 1rem;
    }

    .workspace-error {
        color: #fca5a5;
    }
</style>
