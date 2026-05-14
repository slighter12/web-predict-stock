<script lang="ts">
    import { createEventDispatcher, onMount } from "svelte";

    import { ApiError } from "../api";
    import { loadTwCompanyProfiles } from "../state/twCompanyProfiles";
    import type { MarketCode, TwCompanyProfile } from "../types";

    export let label = "Symbols";
    export let market: MarketCode = "TW";
    export let value: string[] = [];
    export let placeholder = "Search by symbol or company name";
    export let maxSelections: number | null = null;

    const dispatch = createEventDispatcher<{
        change: { value: string[] };
    }>();

    let query = "";
    let profiles: TwCompanyProfile[] = [];
    let isLoading = false;
    let loadError: string | null = null;
    let loadedMarket: MarketCode | null = null;
    let profileMarket: MarketCode | null = null;
    let inputElement: HTMLInputElement;
    const inputId = `symbol-selector-${Math.random().toString(36).slice(2)}`;

    const normalizeSymbol = (symbol: string) => symbol.trim().toUpperCase();

    const emitValue = (nextValue: string[]) => {
        dispatch("change", { value: nextValue });
    };

    const addSymbols = (symbols: string[]) => {
        const normalized = symbols.map(normalizeSymbol).filter(Boolean);
        if (!normalized.length) {
            return;
        }
        const next = [...new Set([...value, ...normalized])];
        emitValue(maxSelections === null ? next : next.slice(-maxSelections));
        query = "";
        if (inputElement) {
            inputElement.value = "";
        }
    };

    export const commitPending = () => {
        if (query.trim()) {
            addSymbols([query]);
        }
    };

    const removeSymbol = (symbol: string) => {
        emitValue(value.filter((item) => item !== symbol));
    };

    const loadProfiles = async () => {
        if (market !== "TW" || loadedMarket === market || isLoading) {
            return;
        }
        isLoading = true;
        try {
            profiles = await loadTwCompanyProfiles();
            loadedMarket = market;
            loadError = null;
        } catch (error) {
            profiles = [];
            loadedMarket = null;
            loadError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Symbol list is unavailable.";
        } finally {
            isLoading = false;
        }
    };

    const handleInput = (event: Event) => {
        const input = event.currentTarget as HTMLInputElement;
        query = input.value;
        if (query.includes(",")) {
            addSymbols(query.split(","));
        }
    };

    const handleKeydown = (event: KeyboardEvent) => {
        if (event.key === "Enter" && query.trim()) {
            event.preventDefault();
            commitPending();
        }
        if (event.key === "Backspace" && !query && value.length) {
            removeSymbol(value[value.length - 1]);
        }
    };

    const matchesQuery = (profile: TwCompanyProfile, normalizedQuery: string) =>
        profile.symbol.includes(normalizedQuery) ||
        profile.company_name.toUpperCase().includes(normalizedQuery) ||
        (profile.industry_category ?? "").toUpperCase().includes(
            normalizedQuery,
        );

    onMount(() => {
        void loadProfiles();
    });

    $: if (market !== profileMarket) {
        profileMarket = market;
        loadedMarket = null;
        profiles = [];
        loadError = null;
        void loadProfiles();
    }

    $: normalizedQuery = query.trim().toUpperCase();
    $: filteredProfiles =
        market === "TW" && normalizedQuery
            ? profiles
                  .filter((profile) => matchesQuery(profile, normalizedQuery))
                  .slice(0, 8)
            : [];
    $: showManualHint =
        !isLoading && (market !== "TW" || Boolean(loadError) || !profiles.length);
</script>

<div class="symbol-selector">
    <label class="selector-label" for={inputId}>{label}</label>
    <div class="selector-control">
        {#each value as symbol}
            <button
                type="button"
                class="symbol-chip"
                aria-label={`Remove ${symbol}`}
                onclick={() => removeSymbol(symbol)}
            >
                {symbol}
                <span aria-hidden="true">x</span>
            </button>
        {/each}
        <input
            bind:this={inputElement}
            id={inputId}
            value={query}
            placeholder={value.length ? "" : placeholder}
            oninput={handleInput}
            onkeydown={handleKeydown}
        />
    </div>

    {#if isLoading}
        <small>Loading symbol list...</small>
    {:else if normalizedQuery && filteredProfiles.length}
        <div class="symbol-options">
            {#each filteredProfiles as profile}
                <button
                    type="button"
                    class="symbol-option"
                    onclick={() => addSymbols([profile.symbol])}
                >
                    <strong>{profile.symbol}</strong>
                    <span>
                        {profile.company_name} · {profile.exchange}
                        {#if profile.industry_category}
                            · {profile.industry_category}
                        {/if}
                    </span>
                </button>
            {/each}
        </div>
    {:else if normalizedQuery}
        <button
            type="button"
            class="manual-option"
            onclick={() => addSymbols([query])}
        >
            Add "{normalizeSymbol(query)}"
        </button>
    {/if}

    {#if showManualHint}
        <small>
            {market === "TW"
                ? "TW symbol list is unavailable; manual symbol entry still works."
                : "US lookup is not connected yet; enter tickers manually."}
            {#if loadError}
                <button
                    type="button"
                    class="retry-link"
                    onclick={() => void loadProfiles()}
                >
                    Retry symbol list
                </button>
            {/if}
        </small>
    {/if}
</div>

<style lang="scss">
    .symbol-selector {
        display: grid;
        gap: 0.45rem;
    }

    .selector-label,
    small {
        color: var(--muted);
    }

    .selector-control {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.45rem;
        min-height: 3.05rem;
        padding: 0.42rem;
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: var(--radius-sm);
        background: rgba(4, 14, 24, 0.88);
    }

    .selector-control:focus-within {
        border-color: rgba(125, 211, 252, 0.48);
        box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.16);
    }

    .selector-control input {
        flex: 1 1 12rem;
        min-width: 9rem;
        border: 0;
        padding: 0.35rem 0.4rem;
        background: transparent;
        box-shadow: none;
    }

    .selector-control input:hover,
    .selector-control input:focus {
        border: 0;
        outline: 0;
        transform: none;
    }

    .symbol-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.38rem 0.55rem;
        border-radius: 999px;
        background: rgba(20, 184, 166, 0.15);
        border-color: rgba(45, 212, 191, 0.34);
        color: #ccfbf1;
        font-weight: 700;
    }

    .symbol-chip span {
        color: var(--muted);
    }

    .retry-link {
        margin-left: 0.5rem;
        padding: 0;
        border: 0;
        background: transparent;
        color: var(--accent-primary);
        font: inherit;
        text-decoration: underline;
    }

    .symbol-options {
        display: grid;
        gap: 0.45rem;
        padding: 0.45rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(5, 15, 26, 0.96);
    }

    .symbol-option,
    .manual-option {
        display: grid;
        gap: 0.2rem;
        text-align: left;
        padding: 0.7rem 0.8rem;
        border-radius: var(--radius-sm);
        background: rgba(10, 25, 40, 0.92);
    }

    .symbol-option span {
        color: var(--muted);
        line-height: 1.35;
    }
</style>
