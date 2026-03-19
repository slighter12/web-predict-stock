<script lang="ts">
    import type { SignalPoint } from "../../types";

    export let signals: SignalPoint[] = [];
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Allocation Trace</p>
            <h3>Signals</h3>
        </div>
        <span>{signals.length} rows</span>
    </div>

    {#if signals.length}
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Symbol</th>
                        <th>Score</th>
                        <th>Position</th>
                    </tr>
                </thead>
                <tbody>
                    {#each signals as signal}
                        <tr>
                            <td>{signal.date}</td>
                            <td>{signal.symbol}</td>
                            <td>{signal.score.toFixed(4)}</td>
                            <td>{signal.position.toFixed(3)}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {:else}
        <p class="muted">
            No active signals are available for the current research run.
        </p>
    {/if}
</div>

<style>
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

    span,
    .muted {
        color: var(--muted);
    }

    .table-wrap {
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: collapse;
    }

    th,
    td {
        text-align: left;
        padding: 0.8rem 0.5rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        white-space: nowrap;
    }
</style>
