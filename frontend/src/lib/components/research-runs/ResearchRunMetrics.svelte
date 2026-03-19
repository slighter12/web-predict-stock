<script lang="ts">
    import MetricCard from "../MetricCard.svelte";

    import type { Metrics } from "../../types";

    export let metrics: Metrics;

    const formatMetric = (value: number | null, suffix = "") =>
        value === null || Number.isNaN(value)
            ? "N/A"
            : `${value.toFixed(3)}${suffix}`;
</script>

<div class="metrics-grid">
    <MetricCard
        label="Total Return"
        value={formatMetric(metrics.total_return)}
        tone={(metrics.total_return ?? 0) >= 0 ? "positive" : "negative"}
    />
    <MetricCard label="Sharpe" value={formatMetric(metrics.sharpe)} />
    <MetricCard
        label="Max Drawdown"
        value={formatMetric(metrics.max_drawdown)}
        tone="negative"
    />
    <MetricCard label="Turnover" value={formatMetric(metrics.turnover)} />
</div>

<style>
    .metrics-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    @media (max-width: 960px) {
        .metrics-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 640px) {
        .metrics-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
