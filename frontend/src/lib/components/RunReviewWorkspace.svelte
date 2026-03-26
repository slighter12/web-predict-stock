<script lang="ts">
    import { onMount } from "svelte";

    import { ApiError, fetchResearchRun, fetchResearchRuns } from "../api";
    import {
        deriveCapabilityIdsFromRun,
        deriveSubmissionSummaryFromRun,
        getCapabilityDefinition,
        summarizeBaselineComparison,
    } from "../state/researchWorkflow";
    import { stringifyJson } from "../state/mappers";
    import type {
        CapabilityReadinessState,
        ComparisonEligibility,
        ResearchCapabilityId,
        ResearchRunResponse,
        ResearchSubmissionSummary,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import EquityChart from "./EquityChart.svelte";
    import ResearchRunMetrics from "./research-runs/ResearchRunMetrics.svelte";
    import ResearchRunSignals from "./research-runs/ResearchRunSignals.svelte";
    import ResearchRunValidation from "./research-runs/ResearchRunValidation.svelte";

    export let capabilityReadiness: Record<
        ResearchCapabilityId,
        CapabilityReadinessState
    >;
    export let latestResult: ResearchRunResponse | null = null;
    export let latestSubmission: ResearchSubmissionSummary | null = null;

    let selectedRunId = "";

    const comparisonLabels: Record<ComparisonEligibility, string> = {
        comparison_metadata_only: "Metadata only",
        sample_window_pending: "Sample window pending",
        strategy_pair_comparable: "Comparable",
        research_only_comparable: "Research-only comparable",
        unresolved_event_quarantine: "Quarantined",
    };

    const getReadiness = (capabilityId: ResearchCapabilityId) =>
        capabilityReadiness[capabilityId];

    const getCapabilityLabel = (capabilityId: ResearchCapabilityId) =>
        getCapabilityDefinition(capabilityId).label;

    let recentRuns: Awaited<ReturnType<typeof fetchResearchRuns>> = [];
    let selectedRecord: Awaited<ReturnType<typeof fetchResearchRun>> | null =
        null;
    let recentRunsError: string | null = null;
    let selectedRunError: string | null = null;
    let isRecentRunsLoading = false;
    let isSelectedRunLoading = false;
    let loadedRunId = "";
    let refreshedForLatestRunId = "";

    const refreshRecentRuns = async () => {
        isRecentRunsLoading = true;
        try {
            recentRuns = await fetchResearchRuns();
            recentRunsError = null;
        } catch (error) {
            recentRuns = [];
            recentRunsError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : error instanceof Error
                      ? error.message
                      : "Unable to load persisted runs.";
        } finally {
            isRecentRunsLoading = false;
        }
    };

    const loadSelectedRun = async (runId: string) => {
        if (!runId.trim()) {
            selectedRecord = null;
            selectedRunError = null;
            loadedRunId = "";
            return;
        }

        isSelectedRunLoading = true;
        try {
            selectedRecord = await fetchResearchRun(runId);
            selectedRunError = null;
            loadedRunId = runId;
        } catch (error) {
            selectedRecord = null;
            loadedRunId = "";
            selectedRunError =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : error instanceof Error
                      ? error.message
                      : "Unable to load persisted run details.";
        } finally {
            isSelectedRunLoading = false;
        }
    };

    const formatEligibility = (
        value: ComparisonEligibility | null | undefined,
    ) => (value ? (comparisonLabels[value] ?? value) : "Unknown");

    const countCapabilityBlockers = (capabilityIds: ResearchCapabilityId[]) =>
        capabilityIds.filter((capabilityId) => {
            const status = getReadiness(capabilityId)?.status;
            return status === "gated" || status === "not_implemented";
        }).length;

    onMount(() => {
        void refreshRecentRuns();
    });

    $: if (latestResult?.run_id && !selectedRunId) {
        selectedRunId = latestResult.run_id;
    }

    $: activeRunId = selectedRunId || latestResult?.run_id || "";
    $: reviewSummary =
        latestSubmission && latestResult?.run_id === activeRunId
            ? latestSubmission
            : selectedRecord
              ? deriveSubmissionSummaryFromRun(selectedRecord)
              : latestResult
                ? deriveSubmissionSummaryFromRun(latestResult)
                : null;
    $: activeCapabilities = selectedRecord
        ? deriveCapabilityIdsFromRun(selectedRecord)
        : latestResult && latestResult.run_id === activeRunId
          ? (reviewSummary?.capabilityIds ??
            deriveCapabilityIdsFromRun(latestResult))
          : [];
    $: baselineSummary =
        latestResult && latestResult.run_id === activeRunId
            ? summarizeBaselineComparison(latestResult)
            : null;
    $: blockerCount = countCapabilityBlockers(activeCapabilities);
    $: if (
        selectedRunId &&
        selectedRunId !== loadedRunId &&
        !isSelectedRunLoading
    ) {
        void loadSelectedRun(selectedRunId);
    }
    $: if (
        latestResult?.run_id &&
        latestResult.run_id !== refreshedForLatestRunId
    ) {
        refreshedForLatestRunId = latestResult.run_id;
        void refreshRecentRuns();
    }
</script>

<WorkspaceSection
    id="run-review-workspace"
    eyebrow="Run Review"
    title="Review the outcome as a research decision, not a debug dump."
    description="Use this surface to understand what ran, whether it beat the baseline, and which capabilities or readiness blockers matter for the next iteration."
>
    <div class="review-shell">
        <section class="surface surface--hero">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Decision Summary</p>
                    <h3>What this run means</h3>
                </div>
                <p class="muted">
                    Load the latest submitted run or pick any persisted run from
                    the registry summary below.
                </p>
            </div>

            <div class="summary-grid">
                <div class="summary-card">
                    <span>Research Setup</span>
                    <strong
                        >{reviewSummary?.templateLabel ??
                            "No run selected"}</strong
                    >
                    <p>
                        {#if reviewSummary}
                            {reviewSummary.modelFamilyLabel} /
                            {reviewSummary.modelVariantLabel}
                        {:else}
                            Submit or load a run to populate the setup summary.
                        {/if}
                    </p>
                </div>
                <div class="summary-card">
                    <span>Baseline Verdict</span>
                    <strong>
                        {#if baselineSummary}
                            {baselineSummary.verdict === "ahead"
                                ? "Ahead of Baseline"
                                : "Behind Baseline"}
                        {:else}
                            No live comparison
                        {/if}
                    </strong>
                    <p>
                        {#if baselineSummary}
                            {baselineSummary.baselineName} delta
                            {baselineSummary.delta.toFixed(3)}
                        {:else}
                            Detailed baseline comparison appears for the latest
                            in-session run.
                        {/if}
                    </p>
                </div>
                <div class="summary-card">
                    <span>Comparison Eligibility</span>
                    <strong>
                        {formatEligibility(
                            selectedRecord?.comparison_eligibility ??
                                latestResult?.comparison_eligibility,
                        )}
                    </strong>
                    <p>
                        Runtime and governance metadata decide whether this run
                        can be treated as a durable comparison candidate.
                    </p>
                </div>
                <div class="summary-card">
                    <span>Readiness Blockers</span>
                    <strong>{blockerCount}</strong>
                    <p>
                        {activeCapabilities.length
                            ? `${activeCapabilities.length} capability path(s) active`
                            : "No capability selection available yet."}
                    </p>
                </div>
            </div>
        </section>

        <section class="surface">
            <div class="surface-header">
                <div>
                    <p class="eyebrow">Registry</p>
                    <h3>Recent persisted runs</h3>
                </div>
                <div class="registry-actions">
                    {#if activeRunId}
                        <span class="muted">Selected: {activeRunId}</span>
                    {/if}
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => void refreshRecentRuns()}
                        disabled={isRecentRunsLoading}
                    >
                        {isRecentRunsLoading ? "Refreshing..." : "Refresh"}
                    </button>
                </div>
            </div>

            {#if recentRunsError}
                <p class="muted">{recentRunsError}</p>
            {:else if isRecentRunsLoading && !recentRuns.length}
                <p class="muted">Loading persisted runs...</p>
            {:else if recentRuns.length}
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Run ID</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th>Market</th>
                                <th>Eligibility</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each recentRuns.slice(0, 6) as run}
                                <tr>
                                    <td>{run.run_id}</td>
                                    <td>{run.status}</td>
                                    <td
                                        >{new Date(
                                            run.created_at,
                                        ).toLocaleString()}</td
                                    >
                                    <td>{run.market ?? "N/A"}</td>
                                    <td>
                                        {formatEligibility(
                                            run.comparison_eligibility,
                                        )}
                                    </td>
                                    <td>
                                        <button
                                            type="button"
                                            class="secondary"
                                            onclick={() =>
                                                (selectedRunId = run.run_id)}
                                        >
                                            Load
                                        </button>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {:else}
                <p class="muted">No persisted runs are available yet.</p>
            {/if}
        </section>

        {#if latestResult && latestResult.run_id === activeRunId}
            <section class="results-shell">
                <div class="surface">
                    <div class="surface-header">
                        <div>
                            <p class="eyebrow">Latest Result</p>
                            <h3>{latestResult.run_id}</h3>
                        </div>
                        <span class="muted">
                            {reviewSummary?.capabilityIds
                                .map((capabilityId) =>
                                    getCapabilityLabel(capabilityId),
                                )
                                .join(", ")}
                        </span>
                    </div>

                    <ResearchRunMetrics metrics={latestResult.metrics} />
                </div>

                <div class="surface">
                    <div class="surface-header">
                        <div>
                            <p class="eyebrow">Performance</p>
                            <h3>Equity Curve</h3>
                        </div>
                    </div>
                    <EquityChart points={latestResult.equity_curve} />
                </div>

                <ResearchRunValidation
                    validation={latestResult.validation}
                    warnings={latestResult.warnings}
                />

                {#if Object.keys(latestResult.baselines).length}
                    <div class="surface">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Baseline Comparison</p>
                                <h3>Comparison Table</h3>
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
                                    {#each Object.entries(latestResult.baselines) as [baseline, metrics]}
                                        <tr>
                                            <td>{baseline}</td>
                                            <td
                                                >{metrics.total_return?.toFixed(
                                                    3,
                                                ) ?? "N/A"}</td
                                            >
                                            <td
                                                >{metrics.sharpe?.toFixed(3) ??
                                                    "N/A"}</td
                                            >
                                            <td
                                                >{metrics.max_drawdown?.toFixed(
                                                    3,
                                                ) ?? "N/A"}</td
                                            >
                                            <td
                                                >{metrics.turnover?.toFixed(
                                                    3,
                                                ) ?? "N/A"}</td
                                            >
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    </div>
                {/if}

                <ResearchRunSignals signals={latestResult.signals} />
            </section>
        {:else if activeRunId}
            <section class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">Loaded Record</p>
                        <h3>{activeRunId}</h3>
                    </div>
                    <button
                        type="button"
                        class="secondary"
                        onclick={() => void loadSelectedRun(activeRunId)}
                        disabled={isSelectedRunLoading}
                    >
                        {isSelectedRunLoading ? "Loading..." : "Reload"}
                    </button>
                </div>

                {#if isSelectedRunLoading}
                    <p class="muted">Loading persisted run details...</p>
                {:else if selectedRunError}
                    <p class="muted">{selectedRunError}</p>
                {:else if selectedRecord}
                    <div class="mini-grid">
                        <div>
                            <strong>Status</strong>
                            <span>{selectedRecord.status}</span>
                        </div>
                        <div>
                            <strong>Runtime Mode</strong>
                            <span>{selectedRecord.runtime_mode ?? "N/A"}</span>
                        </div>
                        <div>
                            <strong>Tradability State</strong>
                            <span
                                >{selectedRecord.tradability_state ??
                                    "N/A"}</span
                            >
                        </div>
                        <div>
                            <strong>Execution Ratio</strong>
                            <span>
                                {selectedRecord.execution_universe_ratio !==
                                null
                                    ? `${(
                                          selectedRecord.execution_universe_ratio *
                                          100
                                      ).toFixed(1)}%`
                                    : "N/A"}
                            </span>
                        </div>
                    </div>
                    <p class="muted">
                        Full curve, signal, and baseline artifacts are only
                        retained for the latest in-session run. Persisted record
                        review focuses on governance and run metadata.
                    </p>
                {:else}
                    <p class="muted">No record is loaded.</p>
                {/if}
            </section>
        {/if}

        <section class="surface">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Governance</p>
                    <h3>Capability readiness for this run</h3>
                </div>
                <p class="muted">
                    Active capabilities inherit the current gate and readiness
                    posture, even when the run itself was created earlier.
                </p>
            </div>

            {#if activeCapabilities.length}
                <div class="governance-grid">
                    {#each activeCapabilities as capabilityId}
                        {@const readiness = getReadiness(capabilityId)}
                        <article class="governance-card">
                            <span>{getCapabilityLabel(capabilityId)}</span>
                            <strong>{readiness?.status ?? "unknown"}</strong>
                            <p>
                                {readiness?.summary ??
                                    "Capability readiness unavailable."}
                            </p>
                        </article>
                    {/each}
                </div>
            {:else}
                <p class="muted">
                    Capability readiness will appear after you submit or load a
                    run.
                </p>
            {/if}
        </section>

        {#if selectedRecord}
            <details class="surface advanced-surface">
                <summary>Advanced metadata</summary>
                <div class="metadata-grid">
                    <div>
                        <p class="eyebrow">Config Sources</p>
                        <pre>{stringifyJson(
                                selectedRecord.config_sources,
                            )}</pre>
                    </div>
                    <div>
                        <p class="eyebrow">Fallback Audit</p>
                        <pre>{stringifyJson(
                                selectedRecord.fallback_audit,
                            )}</pre>
                    </div>
                    <div>
                        <p class="eyebrow">Version Pack</p>
                        <pre>
{stringifyJson({
                                threshold_policy_version:
                                    selectedRecord.threshold_policy_version,
                                price_basis_version:
                                    selectedRecord.price_basis_version,
                                benchmark_comparability_gate:
                                    selectedRecord.benchmark_comparability_gate,
                                comparison_eligibility:
                                    selectedRecord.comparison_eligibility,
                                factor_catalog_version:
                                    selectedRecord.factor_catalog_version,
                                external_lineage_version:
                                    selectedRecord.external_lineage_version,
                                cluster_snapshot_version:
                                    selectedRecord.cluster_snapshot_version,
                                simulation_adapter_version:
                                    selectedRecord.simulation_adapter_version,
                                live_control_version:
                                    selectedRecord.live_control_version,
                                adaptive_contract_version:
                                    selectedRecord.adaptive_contract_version,
                            })}
                        </pre>
                    </div>
                </div>
            </details>
        {/if}
    </div>
</WorkspaceSection>

<style lang="scss">
    .review-shell,
    .summary-grid,
    .governance-grid {
        display: grid;
        gap: var(--space-4);
    }

    .surface--hero {
        gap: var(--space-4);
    }

    .surface-header--stack {
        align-items: flex-start;
        flex-direction: column;
    }

    .summary-grid,
    .governance-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .registry-actions {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .summary-card,
    .governance-card {
        display: grid;
        gap: 0.5rem;
        padding: 1rem;
        border-radius: var(--radius-md);
        background: rgba(6, 18, 30, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .summary-card span,
    .governance-card span {
        color: var(--accent-primary);
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .summary-card strong,
    .governance-card strong {
        font-size: 1rem;
    }

    .summary-card p,
    .governance-card p {
        margin: 0;
        color: var(--muted);
        line-height: 1.5;
    }

    .advanced-surface summary {
        cursor: pointer;
        font-weight: 600;
    }

    @media (max-width: 1200px) {
        .summary-grid,
        .governance-grid {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 720px) {
        .registry-actions {
            align-items: flex-start;
            flex-direction: column;
        }
    }
</style>
