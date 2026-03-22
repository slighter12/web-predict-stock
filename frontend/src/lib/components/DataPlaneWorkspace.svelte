<script lang="ts">
    import AdaptiveWorkflowPanel from "./data-plane/AdaptiveWorkflowPanel.svelte";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import DataIngestionPanel from "./data-plane/DataIngestionPanel.svelte";
    import ExecutionControlPanel from "./data-plane/ExecutionControlPanel.svelte";
    import ExternalSignalPanel from "./data-plane/ExternalSignalPanel.svelte";
    import ImportantEventPanel from "./data-plane/ImportantEventPanel.svelte";
    import LifecyclePanel from "./data-plane/LifecyclePanel.svelte";
    import PeerInferencePanel from "./data-plane/PeerInferencePanel.svelte";
    import RecoveryDrillPanel from "./data-plane/RecoveryDrillPanel.svelte";
    import ReplayPanel from "./data-plane/ReplayPanel.svelte";
    import TickArchivePanel from "./data-plane/TickArchivePanel.svelte";
</script>

<WorkspaceSection
    id="data-plane-workspace"
    eyebrow="Data Plane"
    title="Operational Control Grid"
    description="Event ingestion, replay, lifecycle, execution, and recovery controls grouped by operating rhythm instead of raw endpoint order."
>
    <div class="data-grid">
        <div class="data-grid__item data-grid__wide">
            <RecoveryDrillPanel />
        </div>
        <div class="data-grid__item">
            <DataIngestionPanel />
        </div>
        <div class="data-grid__item">
            <ReplayPanel />
        </div>
        <div class="data-grid__item">
            <LifecyclePanel />
        </div>
        <div class="data-grid__item">
            <ImportantEventPanel />
        </div>
        <div class="data-grid__item data-grid__wide">
            <TickArchivePanel />
        </div>
        <div class="data-grid__item">
            <ExternalSignalPanel />
        </div>
        <div class="data-grid__item">
            <PeerInferencePanel />
        </div>
        <div class="data-grid__item">
            <ExecutionControlPanel />
        </div>
        <div class="data-grid__item data-grid__wide">
            <AdaptiveWorkflowPanel />
        </div>
    </div>
</WorkspaceSection>

<style lang="scss">
    .data-grid {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        gap: 1rem;
    }

    .data-grid__item {
        min-width: 0;
        grid-column: span 6;
    }

    .data-grid__item :global(.surface) {
        height: 100%;
    }

    .data-grid__wide {
        grid-column: span 12;
    }

    @media (max-width: 1100px) {
        .data-grid {
            grid-template-columns: 1fr;
        }

        .data-grid__item,
        .data-grid__wide {
            grid-column: auto;
        }
    }
</style>
