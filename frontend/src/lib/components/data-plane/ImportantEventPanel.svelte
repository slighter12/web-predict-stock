<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createImportantEvent,
        fetchImportantEvents,
    } from "../../api";
    import {
        createDefaultImportantEventForm,
        toDateTimeValue,
    } from "../../state/dataPlaneForms";
    import type {
        ImportantEvent,
        ImportantEventPayload,
        ImportantEventType,
        TimestampSourceClass,
    } from "../../types";

    const importantEventOptions = [
        "listing_status_change",
        "delisting",
        "ticker_change",
        "stock_split",
        "reverse_split",
        "cash_dividend",
        "stock_dividend",
        "capital_reduction",
        "merger",
        "tender_offer",
    ] as const;
    const timestampSourceOptions = [
        "official_exchange",
        "official_issuer",
        "vendor_published",
    ] as const;

    let form: ImportantEventPayload = createDefaultImportantEventForm();
    let records: ImportantEvent[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            records = await fetchImportantEvents();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load important events.";
        }
    };

    const submit = async () => {
        try {
            await createImportantEvent({
                ...form,
                symbol: form.symbol.trim(),
                effective_date: form.effective_date || undefined,
                event_publication_ts: toDateTimeValue(
                    form.event_publication_ts,
                ),
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
                    : "Unable to save important event.";
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
            <h3>Important Events</h3>
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
                    ).value as ImportantEventType)}
            >
                {#each importantEventOptions as eventType}
                    <option value={eventType}>{eventType}</option>
                {/each}
            </select>
        </label>
        <label>
            <span>Timestamp Source</span>
            <select
                value={form.timestamp_source_class}
                onchange={(event) =>
                    (form.timestamp_source_class = (
                        event.currentTarget as HTMLSelectElement
                    ).value as TimestampSourceClass)}
            >
                {#each timestampSourceOptions as sourceType}
                    <option value={sourceType}>{sourceType}</option>
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
            ><span>Publication Time</span><input
                type="datetime-local"
                bind:value={form.event_publication_ts}
            /></label
        >
        <label class="wide"
            ><span>Notes</span><input bind:value={form.notes} /></label
        >
    </div>

    <button type="button" onclick={submit}>Save Important Event</button>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    {#if records.length}
        <div class="list">
            {#each records as record}
                <div class="row">
                    <strong>{record.symbol}</strong>
                    <span
                        >{record.event_type} / {record.event_publication_ts}</span
                    >
                </div>
            {/each}
        </div>
    {/if}
</div>

<style lang="scss">
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
