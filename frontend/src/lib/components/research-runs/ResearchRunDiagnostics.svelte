<script lang="ts">
    import type { RegressionDiagnostics } from "../../types";

    export let diagnostics: RegressionDiagnostics | null = null;

    const formatNumber = (value: number | null | undefined) =>
        value === null || value === undefined ? "N/A" : value.toFixed(4);
</script>

<section class="surface diagnostics-surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Model Diagnostics</p>
            <h3>Regression Quality</h3>
        </div>
    </div>

    {#if diagnostics}
        <div class="diagnostic-grid">
            <div>
                <span>Samples</span>
                <strong>{diagnostics.sample_count}</strong>
            </div>
            <div>
                <span>RMSE</span>
                <strong>{formatNumber(diagnostics.rmse)}</strong>
            </div>
            <div>
                <span>MAE</span>
                <strong>{formatNumber(diagnostics.mae)}</strong>
            </div>
            <div>
                <span>Rank IC</span>
                <strong>{formatNumber(diagnostics.rank_ic)}</strong>
            </div>
            <div>
                <span>Linear IC</span>
                <strong>{formatNumber(diagnostics.linear_ic)}</strong>
            </div>
        </div>

        <div class="diagnostic-columns">
            <div>
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">Actual vs Predicted</p>
                        <h4>Recent Samples</h4>
                    </div>
                </div>
                {#if diagnostics.actual_vs_predicted.length}
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Symbol</th>
                                    <th>Actual</th>
                                    <th>Predicted</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each diagnostics.actual_vs_predicted.slice(-8) as point}
                                    <tr>
                                        <td>{point.date}</td>
                                        <td>{point.symbol}</td>
                                        <td>{formatNumber(point.actual)}</td>
                                        <td>{formatNumber(point.predicted)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <p class="muted">No prediction samples were persisted.</p>
                {/if}
            </div>

            <div>
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">Feature Importance</p>
                        <h4>Top Features</h4>
                    </div>
                </div>
                {#if diagnostics.feature_importance.length}
                    <div class="importance-list">
                        {#each diagnostics.feature_importance.slice(0, 8) as item}
                            <div>
                                <span>{item.feature}</span>
                                <strong>{formatNumber(item.importance)}</strong>
                            </div>
                        {/each}
                    </div>
                {:else}
                    <p class="muted">No feature importance was exposed.</p>
                {/if}
            </div>
        </div>
    {:else}
        <p class="muted">
            Model diagnostics are unavailable for this run. Older persisted
            records may only contain metadata and strategy metrics.
        </p>
    {/if}
</section>

<style lang="scss">
    .diagnostics-surface,
    .diagnostic-columns,
    .importance-list {
        display: grid;
        gap: var(--space-4);
    }

    .diagnostic-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: var(--space-3);
    }

    .diagnostic-grid > div,
    .importance-list > div {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(148, 163, 184, 0.1);
        background: rgba(6, 18, 30, 0.86);
    }

    .diagnostic-grid span,
    .importance-list span {
        color: var(--accent-primary);
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .diagnostic-columns {
        grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.7fr);
    }

    @media (max-width: 1100px) {
        .diagnostic-grid,
        .diagnostic-columns {
            grid-template-columns: 1fr;
        }
    }
</style>
