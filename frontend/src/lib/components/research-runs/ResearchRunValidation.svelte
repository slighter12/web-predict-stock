<script lang="ts">
    import type { ValidationSummary } from "../../types";

    export let validation: ValidationSummary | null = null;
    export let warnings: string[] = [];
</script>

<div class="validation-grid">
    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Validation</p>
                <h3>{validation?.method ?? "Not Requested"}</h3>
            </div>
        </div>
        {#if validation}
            <div class="mini-grid">
                {#each Object.entries(validation.metrics) as [metric, value]}
                    <div>
                        <strong>{metric}</strong>
                        <span>{value.toFixed(3)}</span>
                    </div>
                {/each}
            </div>
        {:else}
            <p class="muted">Validation is disabled for this run.</p>
        {/if}
    </div>

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Research Notes</p>
                <h3>Warnings</h3>
            </div>
        </div>
        {#if warnings.length}
            <ul>
                {#each warnings as warning}
                    <li>{warning}</li>
                {/each}
            </ul>
        {:else}
            <p class="muted">No warnings returned for this run.</p>
        {/if}
    </div>
</div>

<style>
    .validation-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
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
        gap: 1rem;
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

    .mini-grid {
        display: grid;
        gap: 0.85rem;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }

    .mini-grid div {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.66);
    }

    .muted,
    li {
        color: var(--muted);
    }

    ul {
        margin: 0;
        padding-left: 1.1rem;
    }

    @media (max-width: 960px) {
        .validation-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
