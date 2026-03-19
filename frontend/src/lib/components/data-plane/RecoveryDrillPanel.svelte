<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createRecoveryDrill,
        fetchRecoveryDrills,
    } from "../../api";
    import type { RecoveryDrillRecord } from "../../types";

    let form = {
        rawPayloadId: "",
        benchmarkProfileId: "local_manual_v1",
        notes: "",
    };
    let records: RecoveryDrillRecord[] = [];
    let latestRecord: RecoveryDrillRecord | null = null;
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            records = await fetchRecoveryDrills();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load recovery drills.";
        }
    };

    const submit = async () => {
        const rawPayloadInput = form.rawPayloadId.trim();
        const rawPayloadId = rawPayloadInput ? Number(rawPayloadInput) : undefined;
        if (
            rawPayloadInput &&
            (!Number.isInteger(rawPayloadId) || rawPayloadId < 1)
        ) {
            latestRecord = null;
            errorMessage = "Raw Payload ID must be a positive integer when provided.";
            return;
        }

        try {
            latestRecord = await createRecoveryDrill({
                raw_payload_id: rawPayloadId,
                benchmark_profile_id:
                    form.benchmarkProfileId.trim() || undefined,
                notes: form.notes.trim() || undefined,
            });
            errorMessage = null;
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create recovery drill.";
        }
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Data Plane</p>
            <h3>Recovery Drills</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Raw Payload ID</span><input
                bind:value={form.rawPayloadId}
                placeholder="latest successful if blank"
            /></label
        >
        <label
            ><span>Benchmark Profile</span><input
                bind:value={form.benchmarkProfileId}
            /></label
        >
        <label class="wide"
            ><span>Notes</span><input bind:value={form.notes} /></label
        >
    </div>

    <button type="button" onclick={submit}>Create Recovery Drill</button>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}
    {#if latestRecord}<pre>{JSON.stringify(latestRecord, null, 2)}</pre>{/if}

    {#if records.length}
        <div class="list">
            {#each records as record}
                <div class="row">
                    <strong>#{record.id}</strong>
                    <span
                        >{record.status} / raw_payload_id={record.raw_payload_id}</span
                    >
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .surface,
    .form-grid,
    .list {
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
    h3 {
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
    }
    span,
    .muted {
        color: var(--muted);
    }
    input,
    button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }
    .row {
        padding: 0.75rem 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
    }
    pre {
        margin: 0;
        padding: 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
        white-space: pre-wrap;
        word-break: break-word;
        font-family: var(--mono);
        font-size: 0.78rem;
    }
    @media (max-width: 720px) {
        .form-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
