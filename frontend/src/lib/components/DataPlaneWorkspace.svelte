<script lang="ts">
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import DataIngestionPanel from "./data-plane/DataIngestionPanel.svelte";
    import ImportantEventPanel from "./data-plane/ImportantEventPanel.svelte";
    import LifecyclePanel from "./data-plane/LifecyclePanel.svelte";
    import RecoveryDrillPanel from "./data-plane/RecoveryDrillPanel.svelte";
    import ReplayPanel from "./data-plane/ReplayPanel.svelte";
    import TickArchivePanel from "./data-plane/TickArchivePanel.svelte";
</script>

<WorkspaceSection eyebrow="Data Plane" title="Data Plane Workspace">
    <div class="data-grid">
        <DataIngestionPanel />
        <ReplayPanel />
        <RecoveryDrillPanel />
        <LifecyclePanel />
        <ImportantEventPanel />
        <TickArchivePanel />
    </div>
</WorkspaceSection>

<style>
    .data-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
    }

    @media (max-width: 1100px) {
        .data-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
