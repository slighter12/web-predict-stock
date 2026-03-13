<script lang="ts">
  import { createDefaultFormState, availableBaselines } from "../defaults";
  import type {
    BacktestRequest,
    BaselineName,
    DashboardFormState,
    FeatureName,
    FormFeatureRow,
    PriceSource,
  } from "../types";

  export let isSubmitting = false;
  export let onSubmit: (payload: BacktestRequest) => void;

  let form: DashboardFormState = createDefaultFormState();
  let errors: Record<string, string> = {};

  const addFeature = () => {
    form.features = [
      ...form.features,
      {
        id: `feature-${Date.now()}`,
        name: "ma",
        window: 5,
        source: "close",
        shift: 1,
      },
    ];
  };

  const removeFeature = (id: string) => {
    if (form.features.length === 1) {
      return;
    }
    form.features = form.features.filter((feature) => feature.id !== id);
  };

  const toggleBaseline = (baseline: BaselineName) => {
    form.baselines = form.baselines.includes(baseline)
      ? form.baselines.filter((item) => item !== baseline)
      : [...form.baselines, baseline];
  };

  const updateFeature = <K extends keyof FormFeatureRow>(id: string, key: K, value: FormFeatureRow[K]) => {
    form.features = form.features.map((feature) =>
      feature.id === id ? { ...feature, [key]: value } : feature,
    );
  };

  const parseSymbols = () =>
    form.symbolsInput
      .split(",")
      .map((symbol) => symbol.trim())
      .filter(Boolean);

  function validate(): boolean {
    const nextErrors: Record<string, string> = {};
    const symbols = parseSymbols();

    if (!symbols.length) {
      nextErrors.symbolsInput = "Enter at least one symbol.";
    } else if (symbols.length !== new Set(symbols).size) {
      nextErrors.symbolsInput = "Duplicate symbols are not allowed.";
    }
    if (!form.startDate || !form.endDate) {
      nextErrors.dateRange = "Select both start and end dates.";
    } else if (form.startDate > form.endDate) {
      nextErrors.dateRange = "End date must be on or after start date.";
    }
    if (form.horizonDays < 1) {
      nextErrors.horizonDays = "Horizon must be at least 1 day.";
    }
    if (form.threshold < 0) {
      nextErrors.threshold = "Threshold cannot be negative.";
    }
    if (form.topN < 1) {
      nextErrors.topN = "Top N must be at least 1.";
    }
    if (form.slippage < 0 || form.fees < 0) {
      nextErrors.execution = "Fees and slippage cannot be negative.";
    }

    const uniqueFeatures = new Set<string>();
    form.features.forEach((feature) => {
      const featureKey = `${feature.name}-${feature.window}-${feature.source}`;
      if (feature.window < 1 || feature.shift < 0) {
        nextErrors[`feature-${feature.id}`] = "Window must be >= 1 and shift must be >= 0.";
      } else if (uniqueFeatures.has(featureKey)) {
        nextErrors[`feature-${feature.id}`] = "Duplicate feature name/window/source combinations are not allowed.";
      } else {
        uniqueFeatures.add(featureKey);
      }
    });

    if (form.enableValidation) {
      if (form.validationSplits < 1) {
        nextErrors.validationSplits = "Splits must be at least 1.";
      }
      if (form.validationTestSize <= 0 || form.validationTestSize >= 1) {
        nextErrors.validationTestSize = "Test size must be between 0 and 1.";
      }
    }

    errors = nextErrors;
    return Object.keys(nextErrors).length === 0;
  }

  function buildPayload(): BacktestRequest {
    return {
      market: form.market,
      symbols: parseSymbols(),
      date_range: {
        start: form.startDate,
        end: form.endDate,
      },
      return_target: form.returnTarget,
      horizon_days: form.horizonDays,
      features: form.features.map((feature) => ({
        name: feature.name,
        window: feature.window,
        source: feature.source,
        shift: feature.shift,
      })),
      model: {
        type: "xgboost",
        params: {},
      },
      strategy: {
        type: "research_v1",
        threshold: form.threshold,
        top_n: form.topN,
        allow_proactive_sells: form.allowProactiveSells,
      },
      execution: {
        slippage: form.slippage,
        fees: form.fees,
      },
      validation: form.enableValidation
        ? {
            method: form.validationMethod,
            splits: form.validationSplits,
            test_size: form.validationTestSize,
          }
        : undefined,
      baselines: form.baselines,
    };
  }

  function submitForm() {
    if (!validate()) {
      return;
    }
    onSubmit(buildPayload());
  }

  function resetForm() {
    form = createDefaultFormState();
    errors = {};
  }
</script>

<section class="panel">
  <div class="section-header">
    <div>
      <p class="eyebrow">Research Run</p>
      <h2>Backtest Configuration</h2>
    </div>
    <button type="button" class="secondary" onclick={resetForm}>Reset</button>
  </div>

  <div class="group">
    <label>
      <span>Market</span>
      <select bind:value={form.market}>
        <option value={"TW"}>TW</option>
        <option value={"US"}>US</option>
      </select>
    </label>
    <label class="wide">
      <span>Symbols</span>
      <input bind:value={form.symbolsInput} placeholder="2330, 2317, AAPL" />
      {#if errors.symbolsInput}<small>{errors.symbolsInput}</small>{/if}
    </label>
  </div>

  <div class="group dates">
    <label>
      <span>Start Date</span>
      <input type="date" bind:value={form.startDate} />
    </label>
    <label>
      <span>End Date</span>
      <input type="date" bind:value={form.endDate} />
    </label>
    {#if errors.dateRange}<small class="full">{errors.dateRange}</small>{/if}
  </div>

  <div class="group">
    <label>
      <span>Return Target</span>
      <select bind:value={form.returnTarget}>
        <option value="open_to_open">open_to_open</option>
        <option value="close_to_close">close_to_close</option>
        <option value="open_to_close">open_to_close</option>
      </select>
    </label>
    <label>
      <span>Horizon Days</span>
      <input type="number" min="1" bind:value={form.horizonDays} />
      {#if errors.horizonDays}<small>{errors.horizonDays}</small>{/if}
    </label>
  </div>

  <div class="section-header compact">
    <div>
      <p class="eyebrow">Signals</p>
      <h3>Features</h3>
    </div>
    <button type="button" class="secondary" onclick={addFeature}>Add Feature</button>
  </div>

  <div class="feature-list">
    {#each form.features as feature (feature.id)}
      <div class="feature-row">
        <label>
          <span>Name</span>
          <select
            value={feature.name}
            onchange={(event) =>
              updateFeature(feature.id, "name", (event.currentTarget as HTMLSelectElement).value as FeatureName)}
          >
            <option value={"ma"}>ma</option>
            <option value={"rsi"}>rsi</option>
          </select>
        </label>
        <label>
          <span>Window</span>
          <input
            type="number"
            min="1"
            value={feature.window}
            oninput={(event) =>
              updateFeature(feature.id, "window", Number((event.currentTarget as HTMLInputElement).value))}
          />
        </label>
        <label>
          <span>Source</span>
          <select
            value={feature.source}
            onchange={(event) =>
              updateFeature(feature.id, "source", (event.currentTarget as HTMLSelectElement).value as PriceSource)}
          >
            <option value={"open"}>open</option>
            <option value={"high"}>high</option>
            <option value={"low"}>low</option>
            <option value={"close"}>close</option>
            <option value={"volume"}>volume</option>
          </select>
        </label>
        <label>
          <span>Shift</span>
          <input
            type="number"
            min="0"
            value={feature.shift}
            oninput={(event) =>
              updateFeature(feature.id, "shift", Number((event.currentTarget as HTMLInputElement).value))}
          />
        </label>
        <button type="button" class="ghost" onclick={() => removeFeature(feature.id)}>Remove</button>
        {#if errors[`feature-${feature.id}`]}<small class="full">{errors[`feature-${feature.id}`]}</small>{/if}
      </div>
    {/each}
  </div>

  <div class="section-header compact">
    <div>
      <p class="eyebrow">Portfolio</p>
      <h3>Strategy & Execution</h3>
    </div>
  </div>

  <div class="group triple">
    <label>
      <span>Threshold</span>
      <input type="number" min="0" step="0.001" bind:value={form.threshold} />
      {#if errors.threshold}<small>{errors.threshold}</small>{/if}
    </label>
    <label>
      <span>Top N</span>
      <input type="number" min="1" bind:value={form.topN} />
      {#if errors.topN}<small>{errors.topN}</small>{/if}
    </label>
    <label class="toggle">
      <span>Allow Proactive Sells</span>
      <input type="checkbox" bind:checked={form.allowProactiveSells} />
    </label>
  </div>

  <div class="group">
    <label>
      <span>Slippage</span>
      <input type="number" min="0" step="0.001" bind:value={form.slippage} />
    </label>
    <label>
      <span>Fees</span>
      <input type="number" min="0" step="0.001" bind:value={form.fees} />
    </label>
    {#if errors.execution}<small class="full">{errors.execution}</small>{/if}
  </div>

  <div class="section-header compact">
    <div>
      <p class="eyebrow">Evaluation</p>
      <h3>Validation & Baselines</h3>
    </div>
  </div>

  <label class="toggle">
    <span>Enable Validation</span>
    <input type="checkbox" bind:checked={form.enableValidation} />
  </label>

  {#if form.enableValidation}
    <div class="group triple">
      <label>
        <span>Method</span>
        <select bind:value={form.validationMethod}>
          <option value="holdout">holdout</option>
          <option value="walk_forward">walk_forward</option>
          <option value="rolling_window">rolling_window</option>
          <option value="expanding_window">expanding_window</option>
        </select>
      </label>
      <label>
        <span>Splits</span>
        <input type="number" min="1" bind:value={form.validationSplits} />
        {#if errors.validationSplits}<small>{errors.validationSplits}</small>{/if}
      </label>
      <label>
        <span>Test Size</span>
        <input type="number" min="0.01" max="0.99" step="0.01" bind:value={form.validationTestSize} />
        {#if errors.validationTestSize}<small>{errors.validationTestSize}</small>{/if}
      </label>
    </div>
  {/if}

  <fieldset>
    <legend>Baselines</legend>
    <div class="baseline-grid">
      {#each availableBaselines as baseline}
        <label class="baseline">
          <input
            type="checkbox"
            checked={form.baselines.includes(baseline)}
            onchange={() => toggleBaseline(baseline)}
          />
          <span>{baseline}</span>
        </label>
      {/each}
    </div>
  </fieldset>

  <button class="primary" type="button" disabled={isSubmitting} onclick={submitForm}>
    {isSubmitting ? "Running..." : "Run Backtest"}
  </button>
</section>

<style>
  section {
    display: grid;
    gap: 1rem;
  }

  .panel {
    padding: 1.4rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(2, 6, 23, 0.98));
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
  }

  .section-header.compact {
    margin-top: 0.5rem;
  }

  .eyebrow {
    margin: 0 0 0.25rem;
    color: var(--muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  h2,
  h3,
  legend {
    margin: 0;
    font-size: 1rem;
  }

  .group {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .group.triple {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .feature-list {
    display: grid;
    gap: 0.8rem;
  }

  .feature-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
    gap: 0.75rem;
    padding: 0.9rem;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.12);
  }

  label,
  fieldset {
    display: grid;
    gap: 0.45rem;
  }

  .wide,
  .full {
    grid-column: 1 / -1;
  }

  .toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
    border-radius: 16px;
    background: rgba(15, 23, 42, 0.55);
  }

  input,
  select,
  button {
    font: inherit;
  }

  input,
  select {
    width: 100%;
    border-radius: 14px;
    border: 1px solid rgba(148, 163, 184, 0.16);
    background: rgba(15, 23, 42, 0.88);
    color: var(--text);
    padding: 0.8rem 0.9rem;
  }

  fieldset {
    margin: 0;
    padding: 1rem;
    border-radius: 18px;
    border: 1px solid rgba(148, 163, 184, 0.12);
  }

  .baseline-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .baseline {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .primary,
  .secondary,
  .ghost {
    border: none;
    border-radius: 999px;
    padding: 0.85rem 1.2rem;
    cursor: pointer;
  }

  .primary {
    background: linear-gradient(135deg, #f59e0b, #fb7185);
    color: #1f2937;
    font-weight: 700;
  }

  .secondary,
  .ghost {
    background: rgba(148, 163, 184, 0.12);
    color: var(--text);
  }

  small {
    color: #fca5a5;
  }

  @media (max-width: 900px) {
    .group,
    .group.triple,
    .feature-row,
    .baseline-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
