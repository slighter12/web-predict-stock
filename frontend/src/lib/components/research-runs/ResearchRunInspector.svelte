<script lang="ts">
    import EquityChart from "../EquityChart.svelte";
    import ResearchRunMetrics from "./ResearchRunMetrics.svelte";
    import ResearchRunSignals from "./ResearchRunSignals.svelte";
    import ResearchRunValidation from "./ResearchRunValidation.svelte";

    import type {
        AppError,
        HealthResponse,
        ResearchRunRecord,
        ResearchRunResponse,
    } from "../../types";

    export let result: ResearchRunResponse | null = null;
    export let isSubmitting = false;
    export let submitError: AppError | null = null;
    export let registryState: {
        researchRunRecord: ResearchRunRecord | null;
        recordError: string | null;
        isRunLoading: boolean;
        runLookupId: string;
        onRunLookup: (runId: string) => void;
    } = {
        researchRunRecord: null,
        recordError: null,
        isRunLoading: false,
        runLookupId: "",
        onRunLookup: () => {},
    };
    export let healthState: {
        health: HealthResponse | null;
        isHealthLoading: boolean;
        healthError: string | null;
    } = {
        health: null,
        isHealthLoading: false,
        healthError: null,
    };
    export let gateState: {
        gates: import("../../types").ResearchPhaseGateResponse[];
        gateError: string | null;
    } = {
        gates: [],
        gateError: null,
    };

    let lookupInput = "";

    const gateNames: Record<string, string> = {
        P7: "External Data Readiness",
        P8: "Peer and Cluster Coverage",
        P9: "Simulation Setup",
        P10: "Live Control Setup",
        P11: "Adaptive Workflow Readiness",
    };
    const valueLabels: Record<string, string> = {
        runtime_compatibility_mode: "Manual Threshold Mode",
        vnext_spec_mode: "Standard Research Mode",
    };

    $: lookupInput = registryState.runLookupId;

    const serialize = (value: unknown) => JSON.stringify(value, null, 2);
    const submitLookup = () => registryState.onRunLookup(lookupInput);
    const formatRatio = (value: number | null | undefined) =>
        value === null || value === undefined
            ? "N/A"
            : `${(value * 100).toFixed(1)}%`;
    const toLabel = (value: string) =>
        value
            .replace(/^GATE-/, "")
            .replace(/^KPI-/, "")
            .replace(/[_-]+/g, " ")
            .toLowerCase()
            .replace(/\b\w/g, (character) => character.toUpperCase());
    const formatDisplayValue = (value: string | null | undefined) =>
        value === null || value === undefined
            ? "N/A"
            : (valueLabels[value] ?? toLabel(value));
    const getGateTitle = (gateId: string) =>
        Object.entries(gateNames).find(([phase]) =>
            gateId.includes(phase),
        )?.[1] ?? "Readiness Check";
    const summarizeGate = (
        gate: import("../../types").ResearchPhaseGateResponse,
    ) => {
        const metricValues = Object.values(gate.metrics);
        const artifactValues = Object.values(gate.artifacts);

        return {
            passedMetrics: metricValues.filter(
                (metric) => metric.status === "pass",
            ).length,
            totalMetrics: metricValues.length,
            passedArtifacts: artifactValues.filter(
                (artifact) => artifact.status === "pass",
            ).length,
            totalArtifacts: artifactValues.length,
        };
    };
</script>

<div class="results-shell">
    {#if submitError}
        <div class="error-banner" role="alert">
            <strong>{submitError.code}</strong>
            <span>{submitError.message}</span>
            {#if submitError.runId}<span>run ID: {submitError.runId}</span>{/if}
            {#if submitError.requestId}
                <span>request ID: {submitError.requestId}</span>
            {/if}
        </div>
    {/if}

    {#if isSubmitting}
        <div class="status-banner" aria-live="polite">
            <strong>Research run in progress</strong>
            <span>
                The latest results stay visible while the backend completes the
                new run.
            </span>
        </div>
    {/if}

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">System</p>
                <h3>API Health</h3>
            </div>
            {#if healthState.isHealthLoading}
                <span class="muted">Checking...</span>
            {:else if healthState.health}
                <span class="muted"
                    >{healthState.health.status} / {healthState.health
                        .version}</span
                >
            {/if}
        </div>
        {#if healthState.healthError}
            <p class="muted">{healthState.healthError}</p>
        {:else if healthState.health}
            <p class="muted">{healthState.health.service}</p>
        {/if}
    </div>

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Run Registry</p>
                <h3>Saved Run Record</h3>
            </div>
        </div>
        <div class="lookup-row">
            <input bind:value={lookupInput} placeholder="Paste a run ID" />
            <button
                type="button"
                onclick={submitLookup}
                disabled={!lookupInput.trim() || registryState.isRunLoading}
            >
                {registryState.isRunLoading ? "Loading..." : "Load Saved Run"}
            </button>
        </div>

        {#if registryState.recordError}
            <p class="muted">{registryState.recordError}</p>
        {:else if registryState.researchRunRecord}
            <div class="mini-grid">
                <div>
                    <strong>Status</strong>
                    <span>{registryState.researchRunRecord.status}</span>
                </div>
                <div>
                    <strong>Selection Mode</strong>
                    <span
                        >{formatDisplayValue(
                            registryState.researchRunRecord.runtime_mode,
                        )}</span
                    >
                </div>
                <div>
                    <strong>Default Bundle</strong>
                    <span
                        >{registryState.researchRunRecord
                            .default_bundle_version ?? "N/A"}</span
                    >
                </div>
                <div>
                    <strong>Comparison State</strong>
                    <span
                        >{registryState.researchRunRecord
                            .comparison_eligibility ?? "N/A"}</span
                    >
                </div>
                <div>
                    <strong>Tradability State</strong>
                    <span
                        >{registryState.researchRunRecord.tradability_state ??
                            "N/A"}</span
                    >
                </div>
                <div>
                    <strong>Execution Universe</strong>
                    <span
                        >{registryState.researchRunRecord
                            .execution_universe_count ?? "N/A"} / {registryState
                            .researchRunRecord.full_universe_count ??
                            "N/A"}</span
                    >
                </div>
                <div>
                    <strong>Execution Ratio</strong>
                    <span
                        >{formatRatio(
                            registryState.researchRunRecord
                                .execution_universe_ratio,
                        )}</span
                    >
                </div>
                <div>
                    <strong>Monitor Observation</strong>
                    <span
                        >{registryState.researchRunRecord
                            .monitor_observation_status ?? "N/A"}</span
                    >
                </div>
            </div>
            <div class="metadata-grid">
                <div>
                    <p class="eyebrow">Execution Readiness</p>
                    <pre>{serialize({
                            tradability_state:
                                registryState.researchRunRecord
                                    .tradability_state,
                            capacity_screening_active:
                                registryState.researchRunRecord
                                    .capacity_screening_active,
                            missing_feature_policy_state:
                                registryState.researchRunRecord
                                    .missing_feature_policy_state,
                            corporate_event_state:
                                registryState.researchRunRecord
                                    .corporate_event_state,
                            full_universe_count:
                                registryState.researchRunRecord
                                    .full_universe_count,
                            execution_universe_count:
                                registryState.researchRunRecord
                                    .execution_universe_count,
                            execution_universe_ratio:
                                registryState.researchRunRecord
                                    .execution_universe_ratio,
                            stale_mark_days_with_open_positions:
                                registryState.researchRunRecord
                                    .stale_mark_days_with_open_positions,
                            stale_risk_share:
                                registryState.researchRunRecord
                                    .stale_risk_share,
                            monitor_observation_status:
                                registryState.researchRunRecord
                                    .monitor_observation_status,
                        })}</pre>
                </div>
                <div>
                    <p class="eyebrow">Liquidity Buckets</p>
                    <pre>{serialize(
                            registryState.researchRunRecord
                                .liquidity_bucket_coverages,
                        )}</pre>
                </div>
                <div>
                    <p class="eyebrow">Config Sources</p>
                    <pre>{serialize(
                            registryState.researchRunRecord.config_sources,
                        )}</pre>
                </div>
                <div>
                    <p class="eyebrow">Fallback Audit</p>
                    <pre>{serialize(
                            registryState.researchRunRecord.fallback_audit,
                        )}</pre>
                </div>
                <div>
                    <p class="eyebrow">Validation Outcome</p>
                    <pre>{serialize(
                            registryState.researchRunRecord.validation_outcome,
                        )}</pre>
                </div>
                <div>
                    <p class="eyebrow">Governance</p>
                    <pre>{serialize({
                            comparison_review_matrix_version:
                                registryState.researchRunRecord
                                    .comparison_review_matrix_version,
                            scheduled_review_cadence:
                                registryState.researchRunRecord
                                    .scheduled_review_cadence,
                            model_family:
                                registryState.researchRunRecord.model_family,
                            training_output_contract_version:
                                registryState.researchRunRecord
                                    .training_output_contract_version,
                            adoption_comparison_policy_version:
                                registryState.researchRunRecord
                                    .adoption_comparison_policy_version,
                        })}</pre>
                </div>
                <div>
                    <p class="eyebrow">Data and Control Setup</p>
                    <pre>{serialize({
                            factor_catalog_version:
                                registryState.researchRunRecord
                                    .factor_catalog_version,
                            scoring_factor_ids:
                                registryState.researchRunRecord
                                    .scoring_factor_ids,
                            external_signal_policy_version:
                                registryState.researchRunRecord
                                    .external_signal_policy_version,
                            external_lineage_version:
                                registryState.researchRunRecord
                                    .external_lineage_version,
                            cluster_snapshot_version:
                                registryState.researchRunRecord
                                    .cluster_snapshot_version,
                            peer_policy_version:
                                registryState.researchRunRecord
                                    .peer_policy_version,
                            peer_comparison_policy_version:
                                registryState.researchRunRecord
                                    .peer_comparison_policy_version,
                            execution_route:
                                registryState.researchRunRecord.execution_route,
                            simulation_profile_id:
                                registryState.researchRunRecord
                                    .simulation_profile_id,
                            simulation_adapter_version:
                                registryState.researchRunRecord
                                    .simulation_adapter_version,
                            live_control_profile_id:
                                registryState.researchRunRecord
                                    .live_control_profile_id,
                            live_control_version:
                                registryState.researchRunRecord
                                    .live_control_version,
                            adaptive_mode:
                                registryState.researchRunRecord.adaptive_mode,
                            adaptive_profile_id:
                                registryState.researchRunRecord
                                    .adaptive_profile_id,
                            adaptive_contract_version:
                                registryState.researchRunRecord
                                    .adaptive_contract_version,
                            reward_definition_version:
                                registryState.researchRunRecord
                                    .reward_definition_version,
                            state_definition_version:
                                registryState.researchRunRecord
                                    .state_definition_version,
                            rollout_control_version:
                                registryState.researchRunRecord
                                    .rollout_control_version,
                        })}</pre>
                </div>
                <div>
                    <p class="eyebrow">Version Pack</p>
                    <pre>{serialize({
                            threshold_policy_version:
                                registryState.researchRunRecord
                                    .threshold_policy_version,
                            price_basis_version:
                                registryState.researchRunRecord
                                    .price_basis_version,
                            benchmark_comparability_gate:
                                registryState.researchRunRecord
                                    .benchmark_comparability_gate,
                            comparison_eligibility:
                                registryState.researchRunRecord
                                    .comparison_eligibility,
                            investability_screening_active:
                                registryState.researchRunRecord
                                    .investability_screening_active,
                            capacity_screening_version:
                                registryState.researchRunRecord
                                    .capacity_screening_version,
                            adv_basis_version:
                                registryState.researchRunRecord
                                    .adv_basis_version,
                            missing_feature_policy_version:
                                registryState.researchRunRecord
                                    .missing_feature_policy_version,
                            execution_cost_model_version:
                                registryState.researchRunRecord
                                    .execution_cost_model_version,
                            split_policy_version:
                                registryState.researchRunRecord
                                    .split_policy_version,
                            bootstrap_policy_version:
                                registryState.researchRunRecord
                                    .bootstrap_policy_version,
                            ic_overlap_policy_version:
                                registryState.researchRunRecord
                                    .ic_overlap_policy_version,
                            factor_catalog_version:
                                registryState.researchRunRecord
                                    .factor_catalog_version,
                            external_lineage_version:
                                registryState.researchRunRecord
                                    .external_lineage_version,
                            cluster_snapshot_version:
                                registryState.researchRunRecord
                                    .cluster_snapshot_version,
                            peer_comparison_policy_version:
                                registryState.researchRunRecord
                                    .peer_comparison_policy_version,
                            simulation_adapter_version:
                                registryState.researchRunRecord
                                    .simulation_adapter_version,
                            live_control_version:
                                registryState.researchRunRecord
                                    .live_control_version,
                            adaptive_contract_version:
                                registryState.researchRunRecord
                                    .adaptive_contract_version,
                            version_pack_status:
                                registryState.researchRunRecord
                                    .version_pack_status,
                        })}</pre>
                </div>
            </div>
        {:else}
            <p class="muted">
                Create a research run or load a run ID to inspect persisted
                metadata.
            </p>
        {/if}
    </div>

    {#if result}
        <ResearchRunMetrics metrics={result.metrics} />

        <div class="surface">
            <div class="surface-header">
                <div>
                    <p class="eyebrow">Performance</p>
                    <h3>Equity Curve</h3>
                </div>
                <span class="run-id">{result.run_id}</span>
            </div>
            <EquityChart points={result.equity_curve} />
        </div>

        <ResearchRunValidation
            validation={result.validation}
            warnings={result.warnings}
        />

        {#if Object.keys(result.baselines).length}
            <div class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">Comparisons</p>
                        <h3>Baseline Metrics</h3>
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
                                    <td
                                        >{metrics.total_return?.toFixed(3) ??
                                            "N/A"}</td
                                    >
                                    <td
                                        >{metrics.sharpe?.toFixed(3) ??
                                            "N/A"}</td
                                    >
                                    <td
                                        >{metrics.max_drawdown?.toFixed(3) ??
                                            "N/A"}</td
                                    >
                                    <td
                                        >{metrics.turnover?.toFixed(3) ??
                                            "N/A"}</td
                                    >
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            </div>
        {/if}

        <ResearchRunSignals signals={result.signals} />
    {:else}
        <div class="surface">
            <p class="eyebrow">Research Runs</p>
            <h3>No Results Yet</h3>
            <p class="muted">
                Create a research run to populate metrics, validation,
                comparison metadata, and signal traces.
            </p>
        </div>
    {/if}

    <div class="surface">
        <div class="surface-header">
            <div>
                <p class="eyebrow">Readiness</p>
                <h3>Readiness Checks</h3>
            </div>
        </div>
        {#if gateState.gateError}
            <p class="muted">{gateState.gateError}</p>
        {:else if gateState.gates.length}
            <div class="gate-grid">
                {#each gateState.gates as gate}
                    {@const summary = summarizeGate(gate)}
                    <article class="gate-card">
                        <div class="gate-card__header">
                            <div>
                                <p class="eyebrow">Readiness Check</p>
                                <h4>{getGateTitle(gate.gate_id)}</h4>
                            </div>
                            <span
                                class:gate-status={true}
                                class:gate-status--pass={gate.overall_status ===
                                    "pass"}
                                class:gate-status--attention={gate.overall_status !==
                                    "pass"}
                            >
                                {toLabel(gate.overall_status)}
                            </span>
                        </div>

                        <div class="mini-grid">
                            <div>
                                <strong>Metrics</strong>
                                <span
                                    >{summary.passedMetrics} / {summary.totalMetrics}
                                    passing</span
                                >
                            </div>
                            <div>
                                <strong>Artifacts</strong>
                                <span
                                    >{summary.passedArtifacts} / {summary.totalArtifacts}
                                    ready</span
                                >
                            </div>
                        </div>

                        {#if gate.missing_reasons.length}
                            <div class="gate-card__reasons">
                                <strong>Needs Attention</strong>
                                <ul>
                                    {#each gate.missing_reasons as reason}
                                        <li>{toLabel(reason)}</li>
                                    {/each}
                                </ul>
                            </div>
                        {:else}
                            <p class="muted">
                                No missing requirements reported.
                            </p>
                        {/if}
                    </article>
                {/each}
            </div>
        {:else}
            <p class="muted">Readiness summaries are not available yet.</p>
        {/if}
    </div>
</div>

<style lang="scss">
    .results-shell,
    .lookup-row,
    .mini-grid,
    .metadata-grid,
    .gate-grid {
        display: grid;
        gap: 1rem;
    }

    .results-shell {
        position: relative;
    }

    .status-banner {
        display: grid;
        gap: 0.25rem;
        padding: 0.9rem 1rem;
        border-radius: 18px;
        border: 1px solid rgba(125, 211, 252, 0.24);
        background: rgba(8, 47, 73, 0.42);
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

    .muted,
    .run-id {
        color: var(--muted);
    }

    .run-id {
        font-family: var(--mono);
        font-size: 0.82rem;
    }

    .lookup-row {
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .lookup-row input,
    .lookup-row button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }

    .mini-grid {
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }

    .mini-grid div {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.66);
    }

    .metadata-grid {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }

    .gate-grid {
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    }

    .gate-card {
        display: grid;
        gap: 1rem;
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.5);
    }

    .gate-card__header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: start;
    }

    .gate-card h4 {
        margin: 0;
    }

    .gate-status {
        display: inline-flex;
        align-items: center;
        min-height: 2rem;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .gate-status--pass {
        color: #bbf7d0;
        background: rgba(34, 197, 94, 0.16);
    }

    .gate-status--attention {
        color: #fde68a;
        background: rgba(245, 158, 11, 0.16);
    }

    .gate-card__reasons {
        display: grid;
        gap: 0.5rem;
    }

    .gate-card__reasons strong {
        font-size: 0.82rem;
    }

    .gate-card__reasons ul {
        margin: 0;
        padding-left: 1.1rem;
        color: var(--text-secondary);
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

    .error-banner {
        display: grid;
        gap: 0.25rem;
        padding: 1rem;
        border-radius: 18px;
        background: rgba(127, 29, 29, 0.35);
        border: 1px solid rgba(248, 113, 113, 0.3);
    }

    @media (max-width: 720px) {
        .lookup-row {
            grid-template-columns: 1fr;
        }
    }
</style>
