<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createTickArchiveDispatch,
        createTickArchiveImport,
        createTickReplay,
        fetchTickArchiveDispatches,
        fetchTickArchives,
        fetchTickOpsKpis,
        fetchTickReplays,
    } from "../../api";
    import type {
        TickArchiveImportResponse,
        TickArchiveObjectRecord,
        TickArchiveRunRecord,
        TickOpsKpiResponse,
        TickReplayRecord,
    } from "../../types";

    const toLocalDateValue = () => {
        const date = new Date();
        do {
            date.setDate(date.getDate() - 1);
        } while (date.getDay() === 0 || date.getDay() === 6);
        return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
            .toISOString()
            .slice(0, 10);
    };

    let dispatchForm = {
        market: "TW",
        trading_date: toLocalDateValue(),
        notes: "",
    };
    let importForm = {
        market: "TW",
        trading_date: toLocalDateValue(),
        notes: "",
    };
    let replayForm = {
        archiveObjectId: "",
        benchmarkProfileId: "local_manual_v1",
        notes: "",
    };
    let archiveFile: File | null = null;

    let runs: TickArchiveRunRecord[] = [];
    let archives: TickArchiveObjectRecord[] = [];
    let replays: TickReplayRecord[] = [];
    let kpis: TickOpsKpiResponse | null = null;
    let latestRun: TickArchiveRunRecord | null = null;
    let latestImport: TickArchiveImportResponse | null = null;
    let latestReplay: TickReplayRecord | null = null;
    let loadError: string | null = null;
    let actionError: string | null = null;

    const refresh = async () => {
        try {
            const [nextRuns, nextArchives, nextReplays, nextKpis] =
                await Promise.all([
                    fetchTickArchiveDispatches(),
                    fetchTickArchives(),
                    fetchTickReplays(),
                    fetchTickOpsKpis(),
                ]);
            runs = nextRuns;
            archives = nextArchives;
            replays = nextReplays;
            kpis = nextKpis;
            loadError = null;
        } catch (error) {
            loadError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load tick archive data.";
        }
    };

    const submitDispatch = async () => {
        try {
            latestRun = await createTickArchiveDispatch({
                market: "TW",
                trading_date: dispatchForm.trading_date,
                mode: "post_close_crawl",
                notes: dispatchForm.notes.trim() || undefined,
            });
            actionError = null;
            await refresh();
        } catch (error) {
            actionError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create tick archive dispatch.";
        }
    };

    const submitImport = async () => {
        if (!archiveFile) {
            actionError = "Please choose an archive file to import.";
            return;
        }
        try {
            latestImport = await createTickArchiveImport({
                market: "TW",
                trading_date: importForm.trading_date,
                notes: importForm.notes.trim() || undefined,
                archive_file: archiveFile,
            });
            actionError = null;
            await refresh();
        } catch (error) {
            actionError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to import tick archive.";
        }
    };

    const submitReplay = async () => {
        const archiveObjectId = Number(replayForm.archiveObjectId.trim());
        if (!Number.isInteger(archiveObjectId) || archiveObjectId < 1) {
            actionError = "Archive Object ID must be a positive integer.";
            return;
        }
        try {
            latestReplay = await createTickReplay({
                archive_object_id: archiveObjectId,
                benchmark_profile_id:
                    replayForm.benchmarkProfileId.trim() || undefined,
                notes: replayForm.notes.trim() || undefined,
            });
            actionError = null;
            await refresh();
        } catch (error) {
            actionError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to replay tick archive.";
        }
    };

    const handleArchiveFileChange = (event: Event) => {
        const target = event.currentTarget as HTMLInputElement;
        archiveFile = target.files?.[0] ?? null;
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Data Plane</p>
            <h3>Tick Archive</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="section">
        <h4>Post-close Dispatch</h4>
        <div class="form-grid">
            <label
                ><span>Market</span><input
                    bind:value={dispatchForm.market}
                    disabled
                /></label
            >
            <label
                ><span>Trading Date</span><input
                    type="date"
                    bind:value={dispatchForm.trading_date}
                /></label
            >
            <label class="wide"
                ><span>Notes</span><input
                    bind:value={dispatchForm.notes}
                /></label
            >
        </div>
        <button type="button" onclick={submitDispatch}
            >Create Tick Dispatch</button
        >
    </div>

    <div class="section">
        <h4>Manual Import</h4>
        <div class="form-grid">
            <label
                ><span>Market</span><input
                    bind:value={importForm.market}
                    disabled
                /></label
            >
            <label
                ><span>Trading Date</span><input
                    type="date"
                    bind:value={importForm.trading_date}
                /></label
            >
            <label class="wide"
                ><span>Notes</span><input
                    bind:value={importForm.notes}
                /></label
            >
            <label class="wide"
                ><span>Archive File</span><input
                    type="file"
                    accept=".gz,.jsonl"
                    onchange={handleArchiveFileChange}
                /></label
            >
        </div>
        <button type="button" onclick={submitImport}>Import Tick Archive</button
        >
    </div>

    <div class="section">
        <h4>Replay</h4>
        <div class="form-grid">
            <label
                ><span>Archive Object ID</span><input
                    bind:value={replayForm.archiveObjectId}
                    placeholder="archive object id"
                /></label
            >
            <label
                ><span>Benchmark Profile</span><input
                    bind:value={replayForm.benchmarkProfileId}
                /></label
            >
            <label class="wide"
                ><span>Notes</span><input
                    bind:value={replayForm.notes}
                /></label
            >
        </div>
        <button type="button" onclick={submitReplay}>Replay Tick Archive</button
        >
    </div>

    {#if loadError}<p class="muted">{loadError}</p>{/if}
    {#if actionError}<p class="muted">{actionError}</p>{/if}
    {#if latestRun}<pre>{JSON.stringify(latestRun, null, 2)}</pre>{/if}
    {#if latestImport}<pre>{JSON.stringify(latestImport, null, 2)}</pre>{/if}
    {#if latestReplay}<pre>{JSON.stringify(latestReplay, null, 2)}</pre>{/if}

    {#if kpis}
        <div class="kpi-grid">
            {#each Object.entries(kpis.metrics) as [metricId, metric]}
                <div class="kpi-card">
                    <strong>{metricId}</strong>
                    <span>{metric.status}</span>
                    <span>{metric.value ?? "n/a"} {metric.unit ?? ""}</span>
                </div>
            {/each}
        </div>
    {/if}

    {#if runs.length}
        <div class="section list">
            <h4>Recent Runs</h4>
            {#each runs as run}
                <div class="row">
                    <strong>#{run.id}</strong>
                    <span>
                        {run.trigger_mode} / {run.status} / date={run.trading_date}
                        / symbols={run.symbol_count} / requests={run.request_count}
                        / observations={run.observation_count}
                    </span>
                </div>
            {/each}
        </div>
    {/if}

    {#if archives.length}
        <div class="section list">
            <h4>Archive Objects</h4>
            {#each archives as archive}
                <div class="row">
                    <strong>#{archive.id}</strong>
                    <span>
                        run={archive.run_id} / records={archive.record_count} / ratio={(
                            archive.compression_ratio * 100
                        ).toFixed(1)}% /
                        {archive.object_key}
                    </span>
                </div>
            {/each}
        </div>
    {/if}

    {#if replays.length}
        <div class="section list">
            <h4>Restore Runs</h4>
            {#each replays as replay}
                <div class="row">
                    <strong>#{replay.id}</strong>
                    <span>
                        archive={replay.archive_object_id} / {replay.restore_status}
                        / rows={replay.restored_row_count} / throughput={replay.throughput_gb_per_minute ??
                            "n/a"}
                    </span>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style lang="scss">
    .surface,
    .section,
    .form-grid,
    .list,
    .kpi-grid {
        display: grid;
        gap: 0.9rem;
    }
    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }
    .surface-header,
    .row {
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
    h4,
    p {
        margin: 0;
    }
    .form-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .wide {
        grid-column: 1 / -1;
    }
    label {
        display: grid;
        gap: 0.35rem;
        font-size: 0.92rem;
    }
    input {
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.7);
        color: inherit;
        padding: 0.75rem 0.85rem;
    }
    button {
        width: fit-content;
        border: 0;
        border-radius: 999px;
        padding: 0.72rem 1.1rem;
        background: rgba(56, 189, 248, 0.18);
        color: inherit;
        cursor: pointer;
    }
    .muted {
        color: var(--muted);
    }
    .kpi-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .kpi-card {
        display: grid;
        gap: 0.25rem;
        padding: 0.85rem;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(2, 6, 23, 0.38);
    }
    pre {
        overflow: auto;
        border-radius: 16px;
        padding: 0.9rem;
        background: rgba(2, 6, 23, 0.54);
    }
    @media (max-width: 720px) {
        .form-grid,
        .kpi-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
