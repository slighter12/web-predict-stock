<script lang="ts">
    import WorkspaceSection from "../../../components/layout/WorkspaceSection.svelte";
    import DataIngestionPanel from "../../../components/data-plane/DataIngestionPanel.svelte";
    import ReplayPanel from "../../../components/data-plane/ReplayPanel.svelte";
    import RecoveryDrillPanel from "../../../components/data-plane/RecoveryDrillPanel.svelte";
    import TickArchivePanel from "./data-plane/TickArchivePanel.svelte";
    import LifecyclePanel from "../../../components/data-plane/LifecyclePanel.svelte";
    import ImportantEventPanel from "../../../components/data-plane/ImportantEventPanel.svelte";
    import ExternalSignalPanel from "./data-plane/ExternalSignalPanel.svelte";
    import PeerInferencePanel from "./data-plane/PeerInferencePanel.svelte";
    import ExecutionControlPanel from "./data-plane/ExecutionControlPanel.svelte";
    import AdaptiveWorkflowPanel from "./data-plane/AdaptiveWorkflowPanel.svelte";

    const cliPaths = [
        ".venv/bin/python -m scripts.market_data_ingestion",
        ".venv/bin/python -m scripts.dispatch_scheduled_ingestions",
        ".venv/bin/python -m scripts.dispatch_scheduled_recovery_drills",
    ];

    const sections = [
        {
            title: "Data Repair",
            detail: "Use these tools when a symbol needs a manual catch-up, recovery drill, or operator-confirmed fix.",
        },
        {
            title: "Replay And Verification",
            detail: "Replay persisted payloads and verify archive recovery without mixing these controls into the prediction flow.",
        },
        {
            title: "Universe And Event Correction",
            detail: "Correct lifecycle transitions and important events when the curated market state needs manual intervention.",
        },
        {
            title: "Signal And Execution Checks",
            detail: "Inspect factor, peer, execution, and adaptive control surfaces only when the workflow needs operational review.",
        },
    ];
</script>

<WorkspaceSection
    id="maintenance-workspace"
    eyebrow="Maintenance"
    title="Operational repair tools stay available, but off the primary path."
    description="Routine data acquisition belongs to CLI and scripts. This workspace is for replay, repair, event correction, and execution diagnostics when the prediction flow needs intervention."
>
    <div class="maintenance-shell">
        <div class="surface surface--lead">
            <div class="surface-header">
                <div>
                    <p class="eyebrow">Operator Notes</p>
                    <h3>CLI remains the default ingestion path.</h3>
                </div>
            </div>
            <div class="cli-grid">
                {#each cliPaths as command}
                    <code>{command}</code>
                {/each}
            </div>
        </div>

        <div class="section-grid">
            {#each sections as section}
                <article class="section-card">
                    <strong>{section.title}</strong>
                    <p>{section.detail}</p>
                </article>
            {/each}
        </div>

        <section class="maintenance-section">
            <div class="section-copy">
                <p class="eyebrow">Data Repair</p>
                <h3>Repair missing or stale market data</h3>
                <p>
                    Create manual ingestions only when the automated data path
                    needs help. Recovery drills stay here because they validate
                    repair, not prediction logic.
                </p>
            </div>
            <div class="panel-grid panel-grid--split">
                <DataIngestionPanel />
                <RecoveryDrillPanel />
            </div>
        </section>

        <section class="maintenance-section">
            <div class="section-copy">
                <p class="eyebrow">Replay And Verification</p>
                <h3>Rebuild raw payloads and archive state</h3>
                <p>
                    Use replay and tick-archive tools to verify data durability
                    and backfill operations without polluting the prediction
                    builder.
                </p>
            </div>
            <div class="panel-grid panel-grid--stacked">
                <ReplayPanel />
                <TickArchivePanel />
            </div>
        </section>

        <section class="maintenance-section">
            <div class="section-copy">
                <p class="eyebrow">Universe And Events</p>
                <h3>Correct lifecycle and important market events</h3>
                <p>
                    Keep manual lifecycle and event corrections together so the
                    market state can be repaired in one place.
                </p>
            </div>
            <div class="panel-grid panel-grid--split">
                <LifecyclePanel />
                <ImportantEventPanel />
            </div>
        </section>

        <section class="maintenance-section">
            <div class="section-copy">
                <p class="eyebrow">Signal And Execution Checks</p>
                <h3>Inspect non-core operational surfaces</h3>
                <p>
                    Factor, peer, execution, and adaptive controls remain
                    available for diagnostics and manual checks when a run needs
                    deeper operational review.
                </p>
            </div>
            <div class="panel-grid panel-grid--split">
                <ExternalSignalPanel />
                <PeerInferencePanel />
                <ExecutionControlPanel />
                <AdaptiveWorkflowPanel />
            </div>
        </section>
    </div>
</WorkspaceSection>

<style lang="scss">
    .maintenance-shell,
    .cli-grid,
    .section-grid,
    .panel-grid {
        display: grid;
        gap: 1rem;
    }

    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }

    .surface--lead {
        background:
            linear-gradient(
                135deg,
                rgba(21, 47, 31, 0.96),
                rgba(6, 18, 22, 0.92)
            ),
            rgba(15, 23, 42, 0.62);
    }

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
    p,
    strong {
        margin: 0;
    }

    .cli-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    code {
        display: block;
        padding: 0.95rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(134, 239, 172, 0.16);
        background: rgba(2, 6, 23, 0.6);
        font-family: var(--mono);
        font-size: 0.78rem;
        color: var(--text);
        white-space: pre-wrap;
        word-break: break-word;
    }

    .section-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .section-card {
        display: grid;
        gap: 0.45rem;
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(2, 6, 23, 0.46);
    }

    .section-card p,
    .section-copy p {
        color: var(--muted);
        line-height: 1.5;
    }

    .maintenance-section {
        display: grid;
        gap: 1rem;
    }

    .section-copy {
        display: grid;
        gap: 0.45rem;
        max-width: 72ch;
    }

    .panel-grid--split {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        align-items: start;
    }

    .panel-grid--stacked {
        grid-template-columns: 1fr;
    }

    .panel-grid :global(.surface) {
        height: 100%;
    }

    @media (max-width: 1100px) {
        .cli-grid,
        .section-grid,
        .panel-grid--split {
            grid-template-columns: 1fr;
        }
    }
</style>
