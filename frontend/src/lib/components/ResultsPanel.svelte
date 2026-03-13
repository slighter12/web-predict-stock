<script lang="ts">
  import EquityChart from "./EquityChart.svelte";
  import MetricCard from "./MetricCard.svelte";

  import type { AppError, BacktestResponse, HealthResponse } from "../types";

  export let result: BacktestResponse | null = null;
  export let health: HealthResponse | null = null;
  export let isHealthLoading = false;
  export let healthError: string | null = null;
  export let error: AppError | null = null;
  export let isSubmitting = false;

  const formatMetric = (value: number | null, suffix = "") =>
    value === null || Number.isNaN(value) ? "N/A" : `${value.toFixed(3)}${suffix}`;

  const healthTitle = () => {
    if (health?.status === "ok") {
      return "API reachable";
    }
    if (isHealthLoading) {
      return "Checking API";
    }
    return "API unavailable";
  };

  const healthDescription = () => {
    if (health) {
      return `${health.service} v${health.version}`;
    }
    if (isHealthLoading) {
      return "Waiting for health check...";
    }
    return healthError ?? "Health check failed.";
  };
</script>

<section class="panel">
  <div class="hero">
    <div>
      <p class="eyebrow">Execution Surface</p>
      <h1>Quant Research Dashboard</h1>
      <p class="description">Run the live backend contract, inspect portfolio metrics, and review validation output without leaving the same screen.</p>
    </div>
    <div class="status-card">
      <span class:healthy={health?.status === "ok"} class="dot"></span>
      <div>
        <strong>{healthTitle()}</strong>
        <p>{healthDescription()}</p>
      </div>
    </div>
  </div>

  {#if error}
    <div class="error-banner" role="alert">
      <strong>{error.code}</strong>
      <p>{error.message}</p>
      {#if error.requestId}<small>Request ID: {error.requestId}</small>{/if}
    </div>
  {/if}

  {#if result}
    <div class="results-shell">
      {#if isSubmitting}
        <div class="overlay">Refreshing latest run...</div>
      {/if}

      <div class="metrics-grid">
        <MetricCard label="Total Return" value={formatMetric(result.metrics.total_return, "")} tone={(result.metrics.total_return ?? 0) >= 0 ? "positive" : "negative"} />
        <MetricCard label="Sharpe" value={formatMetric(result.metrics.sharpe)} />
        <MetricCard label="Max Drawdown" value={formatMetric(result.metrics.max_drawdown)} tone="negative" />
        <MetricCard label="Turnover" value={formatMetric(result.metrics.turnover)} />
      </div>

      <div class="surface">
        <div class="surface-header">
          <div>
            <p class="eyebrow">Performance</p>
            <h2>Equity Curve</h2>
          </div>
          <span class="run-id">{result.run_id}</span>
        </div>
        <EquityChart points={result.equity_curve} />
      </div>

      {#if result.validation}
        <div class="surface">
          <div class="surface-header">
            <div>
              <p class="eyebrow">Validation</p>
              <h2>{result.validation.method}</h2>
            </div>
          </div>
          <div class="mini-grid">
            {#each Object.entries(result.validation.metrics) as [metric, value]}
              <div>
                <strong>{metric}</strong>
                <span>{value.toFixed(3)}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if Object.keys(result.baselines).length}
        <div class="surface">
          <div class="surface-header">
            <div>
              <p class="eyebrow">Comparisons</p>
              <h2>Baselines</h2>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Baseline</th>
                  <th>Total Return</th>
                  <th>Sharpe</th>
                  <th>Max Drawdown</th>
                  <th>Turnover</th>
                </tr>
              </thead>
              <tbody>
                {#each Object.entries(result.baselines) as [baseline, metrics]}
                  <tr>
                    <td>{baseline}</td>
                    <td>{formatMetric(metrics.total_return ?? null)}</td>
                    <td>{formatMetric(metrics.sharpe ?? null)}</td>
                    <td>{formatMetric(metrics.max_drawdown ?? null)}</td>
                    <td>{formatMetric(metrics.turnover ?? null)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <div class="split-grid">
        <div class="surface">
          <div class="surface-header">
            <div>
              <p class="eyebrow">Risk Notes</p>
              <h2>Warnings</h2>
            </div>
          </div>
          {#if result.warnings.length}
            <ul>
              {#each result.warnings as warning}
                <li>{warning}</li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No warnings returned for this run.</p>
          {/if}
        </div>

        <div class="surface">
          <div class="surface-header">
            <div>
              <p class="eyebrow">Allocation Trace</p>
              <h2>Signals</h2>
            </div>
          </div>
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
                {#each result.signals as signal}
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
        </div>
      </div>
    </div>
  {:else}
    <div class="empty-state">
      <p class="eyebrow">Ready</p>
      <h2>Run a backtest to populate metrics, validation, baselines, and signals.</h2>
      <p>The latest successful result stays on-screen while a new request is running.</p>
    </div>
  {/if}
</section>

<style>
  .panel {
    padding: 1.6rem;
    border-radius: 28px;
    min-height: 100%;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background:
      radial-gradient(circle at top right, rgba(245, 158, 11, 0.16), transparent 36%),
      linear-gradient(180deg, rgba(15, 23, 42, 0.97), rgba(2, 6, 23, 0.99));
    display: grid;
    gap: 1.2rem;
  }

  .hero,
  .surface-header,
  .status-card {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
  }

  h1,
  h2 {
    margin: 0;
  }

  .description,
  .muted,
  .status-card p {
    color: var(--muted);
    margin: 0.45rem 0 0;
  }

  .status-card {
    min-width: 240px;
    padding: 1rem 1.1rem;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.72);
  }

  .dot {
    width: 0.85rem;
    height: 0.85rem;
    border-radius: 999px;
    background: var(--accent-negative);
    box-shadow: 0 0 0 0.4rem rgba(248, 113, 113, 0.12);
  }

  .dot.healthy {
    background: var(--accent-positive);
    box-shadow: 0 0 0 0.4rem rgba(16, 185, 129, 0.12);
  }

  .eyebrow {
    margin: 0 0 0.3rem;
    color: var(--muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .error-banner {
    padding: 1rem 1.1rem;
    border-radius: 18px;
    background: rgba(127, 29, 29, 0.35);
    border: 1px solid rgba(248, 113, 113, 0.4);
  }

  .error-banner p,
  .error-banner small {
    margin: 0.35rem 0 0;
  }

  .results-shell {
    position: relative;
    display: grid;
    gap: 1rem;
  }

  .overlay {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    border-radius: 24px;
    backdrop-filter: blur(6px);
    background: rgba(2, 6, 23, 0.42);
    z-index: 2;
  }

  .metrics-grid,
  .mini-grid,
  .split-grid {
    display: grid;
    gap: 1rem;
  }

  .metrics-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .mini-grid {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  }

  .mini-grid div {
    display: grid;
    gap: 0.35rem;
    padding: 0.9rem;
    border-radius: 16px;
    background: rgba(15, 23, 42, 0.66);
  }

  .surface {
    padding: 1.1rem;
    border-radius: 22px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: rgba(15, 23, 42, 0.62);
  }

  .run-id {
    color: var(--muted);
    font-family: var(--mono);
    font-size: 0.82rem;
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

  ul {
    margin: 0;
    padding-left: 1.15rem;
  }

  .split-grid {
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  }

  .empty-state {
    padding: 2rem;
    border-radius: 24px;
    min-height: 360px;
    display: grid;
    align-content: center;
    gap: 0.65rem;
    border: 1px dashed rgba(148, 163, 184, 0.2);
    background: rgba(15, 23, 42, 0.48);
  }

  @media (max-width: 1100px) {
    .metrics-grid,
    .split-grid {
      grid-template-columns: 1fr;
    }

    .hero {
      flex-direction: column;
      align-items: flex-start;
    }

    .status-card {
      min-width: 0;
      width: 100%;
    }
  }
</style>
