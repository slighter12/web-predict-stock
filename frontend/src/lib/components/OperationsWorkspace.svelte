<script lang="ts">
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import DataIngestionPanel from "./data-plane/DataIngestionPanel.svelte";
    import ReplayPanel from "./data-plane/ReplayPanel.svelte";
    import RecoveryDrillPanel from "./data-plane/RecoveryDrillPanel.svelte";
    import TickArchivePanel from "./data-plane/TickArchivePanel.svelte";
    import LifecyclePanel from "./data-plane/LifecyclePanel.svelte";
    import ImportantEventPanel from "./data-plane/ImportantEventPanel.svelte";

    const sections = [
        {
            title: "Ingestion Recovery",
            detail: "Manual catch-up and scheduled recovery stay here so the research flow does not turn into an operator console.",
        },
        {
            title: "Replay And Archive",
            detail: "Replay, tick archive, and verification remain operational surfaces for data durability work.",
        },
        {
            title: "Lifecycle Repair",
            detail: "Lifecycle transitions and important events stay grouped as curated market-state corrections.",
        },
    ];
</script>

<WorkspaceSection
    id="operations-workspace"
    eyebrow="Operations"
    title="Keep repair, replay, and correction workflows out of the main research path."
    description="Operations is intentionally narrow in v2. Factor, peer, and adaptive setup now start from Research; this surface is only for data repair, replay, and market-state correction."
>
    <div class="operations-shell">
        <section class="surface surface--overview">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Operational Scope</p>
                    <h3>What still belongs here</h3>
                </div>
                <p class="muted">
                    Use this area only when the workflow needs a data-plane fix.
                    Research setup and capability expansion now stay inside the
                    primary research experience.
                </p>
            </div>

            <div class="section-grid">
                {#each sections as section}
                    <article class="section-card">
                        <strong>{section.title}</strong>
                        <p>{section.detail}</p>
                    </article>
                {/each}
            </div>
        </section>

        <section class="surface">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Ingestion Recovery</p>
                    <h3>Repair missing or stale market data</h3>
                </div>
                <p class="muted">
                    Manual ingestions and recovery drills stay available when
                    automated acquisition needs intervention.
                </p>
            </div>

            <div class="panel-grid">
                <DataIngestionPanel />
                <RecoveryDrillPanel />
            </div>
        </section>

        <section class="surface">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Replay And Archive</p>
                    <h3>Verify raw payload and archive durability</h3>
                </div>
                <p class="muted">
                    Replay and tick archive operations remain separate so the
                    research flow does not become a maintenance console.
                </p>
            </div>

            <div class="panel-grid panel-grid--stacked">
                <ReplayPanel />
                <TickArchivePanel />
            </div>
        </section>

        <section class="surface">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Market-State Correction</p>
                    <h3>Fix lifecycle and important events</h3>
                </div>
                <p class="muted">
                    Keep manual event and lifecycle repair together so the
                    execution universe remains point-in-time correct.
                </p>
            </div>

            <div class="panel-grid">
                <LifecyclePanel />
                <ImportantEventPanel />
            </div>
        </section>
    </div>
</WorkspaceSection>

<style lang="scss">
    .operations-shell,
    .section-grid,
    .panel-grid {
        display: grid;
        gap: var(--space-4);
    }

    .surface--overview {
        gap: var(--space-4);
    }

    .surface-header--stack {
        align-items: flex-start;
        flex-direction: column;
    }

    .section-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .section-card {
        display: grid;
        gap: 0.5rem;
        padding: 1rem;
        border-radius: var(--radius-md);
        background: rgba(6, 18, 30, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .section-card p {
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
    }

    .panel-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        align-items: start;
    }

    .panel-grid--stacked {
        grid-template-columns: 1fr;
    }

    @media (max-width: 1100px) {
        .section-grid,
        .panel-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
