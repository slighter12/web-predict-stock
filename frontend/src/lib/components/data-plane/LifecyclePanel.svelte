<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createLifecycleRecord,
        fetchLifecycleRecords,
    } from "../../api";
    import { createDefaultLifecycleRecordForm } from "../../state/dataPlaneForms";
    import type {
        LifecycleEventType,
        LifecycleRecord,
        LifecycleRecordPayload,
    } from "../../types";

    const lifecycleEventOptions = [
        "listing",
        "delisting",
        "ticker_change",
        "re_listing",
    ] as const;

    let form: LifecycleRecordPayload = createDefaultLifecycleRecordForm();
    let records: LifecycleRecord[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            records = await fetchLifecycleRecords();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load lifecycle records.";
        }
    };

    const submit = async () => {
        try {
            await createLifecycleRecord({
                ...form,
                symbol: form.symbol.trim(),
                reference_symbol: form.reference_symbol?.trim() || undefined,
                archive_object_reference:
                    form.archive_object_reference?.trim() || undefined,
                notes: form.notes?.trim() || undefined,
            });
            errorMessage = null;
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to save lifecycle record.";
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
            <h3>Lifecycle Records</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label><span>Symbol</span><input bind:value={form.symbol} /></label>
        <label>
            <span>Market</span>
            <select bind:value={form.market}>
                <option value="TW">TW</option>
                <option value="US">US</option>
            </select>
        </label>
        <label>
            <span>Event Type</span>
            <select
                value={form.event_type}
                onchange={(event) =>
                    (form.event_type = (
                        event.currentTarget as HTMLSelectElement
                    ).value as LifecycleEventType)}
            >
                {#each lifecycleEventOptions as eventType}
                    <option value={eventType}>{eventType}</option>
                {/each}
            </select>
        </label>
        <label
            ><span>Effective Date</span><input
                type="date"
                bind:value={form.effective_date}
            /></label
        >
        <label
            ><span>Reference Symbol</span><input
                bind:value={form.reference_symbol}
            /></label
        >
        <label
            ><span>Source Name</span><input
                bind:value={form.source_name}
            /></label
        >
        <label class="wide"
            ><span>Notes</span><input bind:value={form.notes} /></label
        >
    </div>

    <button type="button" onclick={submit}>Save Lifecycle Record</button>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    {#if records.length}
        <div class="list">
            {#each records as record}
                <div class="row">
                    <strong>{record.symbol}</strong>
                    <span>{record.event_type} / {record.effective_date}</span>
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
    select,
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
    @media (max-width: 720px) {
        .form-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
