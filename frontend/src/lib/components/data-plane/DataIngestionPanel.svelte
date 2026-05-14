<script lang="ts">
    import { ApiError, createDataIngestion } from "../../api";
    import type { DataIngestionResponse, MarketCode } from "../../types";
    import SymbolSelector from "../SymbolSelector.svelte";

    let form: {
        symbol: string;
        market: MarketCode;
        years: string;
        dateStr: string;
    } = {
        symbol: "2330",
        market: "TW",
        years: "5",
        dateStr: "",
    };
    let result: DataIngestionResponse | null = null;
    let errorMessage: string | null = null;
    let symbolSelector: { commitPending: () => void } | null = null;

    const setSymbol = (symbols: string[]) => {
        form.symbol = symbols[0] ?? "";
    };

    const formatSummary = (data: DataIngestionResponse) =>
        `Backfill ${data.backfill.upserted_rows} rows, daily update ${data.daily_update.upserted_rows} rows, minute supplement ${data.minute_supplement.status}.`;

    const submit = async () => {
        symbolSelector?.commitPending();
        try {
            result = await createDataIngestion({
                symbol: form.symbol.trim(),
                market: form.market,
                years: Number(form.years),
                date_str: form.dateStr.trim() || undefined,
            });
            errorMessage = null;
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to ingest market data.";
        }
    };
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Data Plane</p>
            <h3>Sync Market Data</h3>
        </div>
    </div>

    <div class="form-grid">
        <SymbolSelector
            bind:this={symbolSelector}
            label="Symbol"
            market={form.market}
            value={form.symbol ? [form.symbol] : []}
            placeholder="Search 2330 or enter ticker"
            maxSelections={1}
            on:change={(event) => setSymbol(event.detail.value)}
        />
        <label>
            <span>Market</span>
            <select bind:value={form.market}>
                <option value="TW">TW</option>
                <option value="US">US</option>
            </select>
        </label>
        <label
            ><span>Years</span><input
                type="number"
                min="1"
                bind:value={form.years}
            /></label
        >
        <label
            ><span>Date Override</span><input
                bind:value={form.dateStr}
                placeholder="20240101"
            /></label
        >
    </div>

    <button type="button" class="submit" onclick={submit}>
        Sync Market Data
    </button>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}
    {#if result}
        <div class="sync-summary">
            <strong>{formatSummary(result)}</strong>
            <span>
                Raw payloads:
                {result.backfill.raw_payload_id ?? "N/A"} /
                {result.daily_update.raw_payload_id ?? "N/A"}
            </span>
        </div>
        <details>
            <summary>Advanced sync payload</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
        </details>
    {/if}
</div>

<style lang="scss">
    .surface,
    .form-grid {
        display: grid;
        gap: 0.9rem;
    }
    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }
    .surface-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
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
    .sync-summary {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border-radius: var(--radius-md);
        background: rgba(20, 184, 166, 0.12);
        border: 1px solid rgba(45, 212, 191, 0.22);
    }
    .sync-summary span,
    details summary {
        color: var(--muted);
    }
    details {
        display: grid;
        gap: 0.75rem;
    }
    details summary {
        cursor: pointer;
        font-weight: 600;
    }
    @media (max-width: 720px) {
        .form-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
