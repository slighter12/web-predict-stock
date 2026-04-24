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
        ResearchRunRecord,
        ResearchRunResponse,
        ResearchSubmissionSummary,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import EquityChart from "./EquityChart.svelte";
    import ResearchRunDiagnostics from "./research-runs/ResearchRunDiagnostics.svelte";
    import ResearchRunMetrics from "./research-runs/ResearchRunMetrics.svelte";
    import ResearchRunSignals from "./research-runs/ResearchRunSignals.svelte";
    import ResearchRunValidation from "./research-runs/ResearchRunValidation.svelte";

    export let capabilityReadiness: Record<
        ResearchCapabilityId,
        CapabilityReadinessState
    >;
    export let latestResult: ResearchRunResponse | null = null;
    export let latestSubmission: ResearchSubmissionSummary | null = null;

    type SortKey = "created_desc" | "created_asc" | "return_desc" | "rmse_asc";
    type ReviewRun = ResearchRunRecord | ResearchRunResponse;
    type ComparisonSeverity = "blocker" | "note";
    type ComparisonFinding = {
        label: string;
        detail: string;
        severity: ComparisonSeverity;
    };
    type RunComparisonFields = {
        datasetLabel: string;
        datasetSignature: string;
        targetLabel: string;
        targetSignature: string;
        featureLabel: string;
        featureSignature: string;
        modelLabel: string;
        modelSignature: string;
        costLabel: string;
        costSignature: string;
    };

    let selectedRunId = "";
    let searchQuery = "";
    let statusFilter = "all";
    let sortKey: SortKey = "created_desc";
    let selectedCompareIds: string[] = [];

    const comparisonLabels: Record<ComparisonEligibility, string> = {
        comparison_metadata_only: "Metadata only",
        sample_window_pending: "Sample window pending",
        strategy_pair_comparable: "Comparable",
        research_only_comparable: "Research-only comparable",
        unresolved_event_quarantine: "Quarantined",
    };

    let recentRuns: ResearchRunRecord[] = [];
    let selectedRecord: ResearchRunRecord | null = null;
    let recentRunsError: string | null = null;
    let selectedRunError: string | null = null;
    let isRecentRunsLoading = false;
    let isSelectedRunLoading = false;
    let loadedRunId = "";
    let refreshedForLatestRunId = "";
    let selectedForLatestRunId = "";

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

    const getReadiness = (capabilityId: ResearchCapabilityId) =>
        capabilityReadiness[capabilityId];

    const getCapabilityLabel = (capabilityId: ResearchCapabilityId) =>
        getCapabilityDefinition(capabilityId).label;

    const countCapabilityBlockers = (capabilityIds: ResearchCapabilityId[]) =>
        capabilityIds.filter((capabilityId) => {
            const status = getReadiness(capabilityId)?.status;
            return status === "gated" || status === "not_implemented";
        }).length;

    const hasCompleteArtifacts = (run: ReviewRun | null) =>
        Boolean(
            run?.model_diagnostics ||
                run?.equity_curve?.length ||
                run?.signals?.length ||
                Object.keys(run?.baselines ?? {}).length,
        );

    const formatMetric = (value: number | null | undefined) =>
        value === null || value === undefined ? "N/A" : value.toFixed(4);

    const getPayloadArray = (
        payload: Record<string, unknown> | null | undefined,
        key: string,
    ) => {
        const value = payload?.[key];
        return Array.isArray(value) ? value : [];
    };

    const getPayloadText = (
        payload: Record<string, unknown> | null | undefined,
        key: string,
    ) => {
        const value = payload?.[key];
        return value === null || value === undefined ? "N/A" : String(value);
    };

    const isRecord = (value: unknown): value is Record<string, unknown> =>
        typeof value === "object" && value !== null && !Array.isArray(value);

    const normalizeForSignature = (value: unknown): unknown => {
        if (Array.isArray(value)) {
            return value.map(normalizeForSignature);
        }
        if (!isRecord(value)) {
            return value;
        }
        return Object.fromEntries(
            Object.entries(value)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([key, entry]) => [key, normalizeForSignature(entry)]),
        );
    };

    const stableStringify = (value: unknown) =>
        JSON.stringify(normalizeForSignature(value));

    const uniqueValues = (values: string[]) => [...new Set(values)];

    const getPayloadObject = (
        payload: Record<string, unknown> | null | undefined,
        key: string,
    ) => {
        const value = payload?.[key];
        return isRecord(value) ? value : null;
    };

    const getSymbols = (run: ResearchRunRecord) => {
        const payloadSymbols = getPayloadArray(run.request_payload, "symbols")
            .filter((symbol): symbol is string => typeof symbol === "string")
            .sort();
        return payloadSymbols.length ? payloadSymbols : [...run.symbols].sort();
    };

    const getDateRangeParts = (
        payload: Record<string, unknown> | null | undefined,
    ) => {
        const dateRange = getPayloadObject(payload, "date_range");
        return {
            start: getPayloadText(dateRange, "start"),
            end: getPayloadText(dateRange, "end"),
        };
    };

    const getFeatureSignature = (
        payload: Record<string, unknown> | null | undefined,
    ) => {
        const features = getPayloadArray(payload, "features");
        return features
            .map((feature) => {
                if (!isRecord(feature)) {
                    return String(feature);
                }
                return stableStringify({
                    name: feature.name,
                    source: feature.source,
                    window: feature.window,
                    shift: feature.shift,
                });
            })
            .sort()
            .join("|");
    };

    const getFeatureLabel = (
        payload: Record<string, unknown> | null | undefined,
    ) => {
        const features = getPayloadArray(payload, "features");
        return features.length ? `${features.length} features` : "N/A";
    };

    const getModelFields = (
        payload: Record<string, unknown> | null | undefined,
    ) => {
        const model = getPayloadObject(payload, "model");
        if (!model) {
            return { label: "N/A", signature: "N/A" };
        }
        const modelType = getPayloadText(model, "type");
        const params = getPayloadObject(model, "params");
        const paramsSignature = params ? stableStringify(params) : "{}";
        return {
            label: paramsSignature === "{}" ? modelType : `${modelType} params`,
            signature: stableStringify(model),
        };
    };

    const getCostFields = (run: ResearchRunRecord) => {
        const execution = getPayloadObject(run.request_payload, "execution");
        const slippage = getPayloadText(execution, "slippage");
        const fees = getPayloadText(execution, "fees");
        const version = run.execution_cost_model_version ?? "N/A";
        return {
            label: `fee ${fees} / slip ${slippage}`,
            signature: stableStringify({
                execution,
                execution_cost_model_version: version,
                price_basis_version: run.price_basis_version,
            }),
        };
    };

    const getComparisonFields = (run: ResearchRunRecord): RunComparisonFields => {
        const symbols = getSymbols(run);
        const dateRange = getDateRangeParts(run.request_payload);
        const model = getModelFields(run.request_payload);
        const cost = getCostFields(run);
        const targetLabel = `${getPayloadText(
            run.request_payload,
            "return_target",
        )} / ${getPayloadText(run.request_payload, "horizon_days")}d`;
        const datasetLabel = `${run.market ?? "N/A"} / ${
            symbols.length ? symbols.join(", ") : "N/A"
        } / ${dateRange.start} to ${dateRange.end}`;

        return {
            datasetLabel,
            datasetSignature: stableStringify({
                market: run.market,
                symbols,
                date_range: dateRange,
            }),
            targetLabel,
            targetSignature: stableStringify({
                return_target: getPayloadText(
                    run.request_payload,
                    "return_target",
                ),
                horizon_days: getPayloadText(
                    run.request_payload,
                    "horizon_days",
                ),
            }),
            featureLabel: getFeatureLabel(run.request_payload),
            featureSignature: getFeatureSignature(run.request_payload) || "N/A",
            modelLabel: model.label,
            modelSignature: model.signature,
            costLabel: cost.label,
            costSignature: cost.signature,
        };
    };

    const getComparisonAssessment = (runs: ResearchRunRecord[]) => {
        const fields = runs.map(getComparisonFields);
        const findings: ComparisonFinding[] = [];

        if (runs.some((run) => !hasCompleteArtifacts(run))) {
            findings.push({
                label: "Missing artifacts",
                detail: "At least one selected run has only metadata-level results.",
                severity: "blocker",
            });
        }
        if (
            runs.some(
                (run) =>
                    run.comparison_eligibility ===
                    "unresolved_event_quarantine",
            )
        ) {
            findings.push({
                label: "Event quarantine",
                detail: "At least one selected run has unresolved event state.",
                severity: "blocker",
            });
        }
        if (uniqueValues(fields.map((field) => field.datasetSignature)).length > 1) {
            findings.push({
                label: "Dataset differs",
                detail: "Market, symbols, or date range are not aligned.",
                severity: "blocker",
            });
        }
        if (uniqueValues(fields.map((field) => field.targetSignature)).length > 1) {
            findings.push({
                label: "Target differs",
                detail: "Return target or horizon are not aligned.",
                severity: "blocker",
            });
        }
        if (uniqueValues(fields.map((field) => field.costSignature)).length > 1) {
            findings.push({
                label: "Cost basis differs",
                detail: "Execution cost or price basis versions are not aligned.",
                severity: "blocker",
            });
        }
        if (uniqueValues(fields.map((field) => field.featureSignature)).length > 1) {
            findings.push({
                label: "Feature set differs",
                detail: "Treat quality deltas as feature-ablation evidence.",
                severity: "note",
            });
        }
        if (uniqueValues(fields.map((field) => field.modelSignature)).length > 1) {
            findings.push({
                label: "Model config differs",
                detail: "This is a model experiment, not a repeated run.",
                severity: "note",
            });
        }

        const blockers = findings.filter(
            (finding) => finding.severity === "blocker",
        );

        return {
            status: blockers.length
                ? "Limited comparison"
                : "Comparable research review",
            findings,
        };
    };

    const compareToggle = (runId: string, checked: boolean) => {
        selectedCompareIds = checked
            ? [...new Set([...selectedCompareIds, runId])]
            : selectedCompareIds.filter((item) => item !== runId);
    };

    const getComparableReason = (run: ReviewRun) => {
        if (!hasCompleteArtifacts(run)) {
            return "Missing persisted result artifacts.";
        }
        if (run.comparison_eligibility === "comparison_metadata_only") {
            return "Only metadata-level comparison is available.";
        }
        if (run.comparison_eligibility === "unresolved_event_quarantine") {
            return "Blocked by unresolved event state.";
        }
        return "Comparable for research review.";
    };

    onMount(() => {
        void refreshRecentRuns();
    });

    $: if (
        latestResult?.run_id &&
        latestResult.run_id !== selectedForLatestRunId
    ) {
        selectedForLatestRunId = latestResult.run_id;
        selectedRunId = latestResult.run_id;
    }

    $: activeRunId = selectedRunId || latestResult?.run_id || "";
    $: activeRun =
        latestResult && latestResult.run_id === activeRunId
            ? latestResult
            : selectedRecord;
    $: metadataRun = activeRun;
    $: reviewSummary =
        latestSubmission && latestResult?.run_id === activeRunId
            ? latestSubmission
            : activeRun
              ? deriveSubmissionSummaryFromRun(activeRun)
              : null;
    $: activeCapabilities = activeRun ? deriveCapabilityIdsFromRun(activeRun) : [];
    $: baselineSummary = summarizeBaselineComparison(activeRun);
    $: blockerCount = countCapabilityBlockers(activeCapabilities);
    $: filteredRuns = recentRuns
        .filter((run) => {
            const query = searchQuery.trim().toLowerCase();
            const matchesSearch =
                !query ||
                run.run_id.toLowerCase().includes(query) ||
                (run.market ?? "").toLowerCase().includes(query) ||
                run.symbols.join(",").toLowerCase().includes(query);
            const matchesStatus =
                statusFilter === "all" || run.status === statusFilter;
            return matchesSearch && matchesStatus;
        })
        .sort((a, b) => {
            if (sortKey === "created_asc") {
                return (
                    new Date(a.created_at).getTime() -
                    new Date(b.created_at).getTime()
                );
            }
            if (sortKey === "return_desc") {
                return (
                    (b.metrics?.total_return ?? Number.NEGATIVE_INFINITY) -
                    (a.metrics?.total_return ?? Number.NEGATIVE_INFINITY)
                );
            }
            if (sortKey === "rmse_asc") {
                return (
                    (a.model_diagnostics?.rmse ?? Number.POSITIVE_INFINITY) -
                    (b.model_diagnostics?.rmse ?? Number.POSITIVE_INFINITY)
                );
            }
            return (
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime()
            );
        });
    $: comparisonRuns = recentRuns.filter((run) =>
        selectedCompareIds.includes(run.run_id),
    );
    $: comparisonAssessment = getComparisonAssessment(comparisonRuns);
    $: if (
        selectedRunId &&
        selectedRunId !== loadedRunId &&
        latestResult?.run_id !== selectedRunId &&
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
    eyebrow="Experiments"
    title="Review persisted experiments with the same result surface."
    description="Use model diagnostics first, then strategy artifacts, baselines, and comparison caveats."
>
    <div class="review-shell">
        <section class="surface surface--hero">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Decision Summary</p>
                    <h3>What this run means</h3>
                </div>
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
                    <span>Model Quality</span>
                    <strong>{formatMetric(activeRun?.model_diagnostics?.rmse)}</strong>
                    <p>RMSE is shown before strategy interpretation.</p>
                </div>
                <div class="summary-card">
                    <span>Baseline Delta</span>
                    <strong>
                        {#if baselineSummary}
                            {formatMetric(baselineSummary.delta)}
                        {:else}
                            N/A
                        {/if}
                    </strong>
                    <p>
                        {baselineSummary?.baselineName ??
                            "No baseline metrics available."}
                    </p>
                </div>
                <div class="summary-card">
                    <span>Comparison Eligibility</span>
                    <strong>
                        {formatEligibility(activeRun?.comparison_eligibility)}
                    </strong>
                    <p>{activeRun ? getComparableReason(activeRun as ResearchRunRecord) : "No run selected."}</p>
                </div>
            </div>
        </section>

        <section class="surface">
            <div class="surface-header">
                <div>
                    <p class="eyebrow">Registry</p>
                    <h3>Recent persisted runs</h3>
                </div>
                <button
                    type="button"
                    class="secondary"
                    onclick={() => void refreshRecentRuns()}
                    disabled={isRecentRunsLoading}
                >
                    {isRecentRunsLoading ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <div class="registry-controls">
                <label>
                    <span>Search</span>
                    <input
                        bind:value={searchQuery}
                        placeholder="run id, market, or symbol"
                    />
                </label>
                <label>
                    <span>Status</span>
                    <select bind:value={statusFilter}>
                        <option value="all">All</option>
                        <option value="succeeded">Succeeded</option>
                        <option value="failed">Failed</option>
                        <option value="rejected">Rejected</option>
                        <option value="validation_failed"
                            >Validation Failed</option
                        >
                        <option value="running">Running</option>
                    </select>
                </label>
                <label>
                    <span>Sort</span>
                    <select bind:value={sortKey}>
                        <option value="created_desc">Newest</option>
                        <option value="created_asc">Oldest</option>
                        <option value="return_desc">Total Return</option>
                        <option value="rmse_asc">RMSE</option>
                    </select>
                </label>
            </div>

            {#if recentRunsError}
                <p class="muted">{recentRunsError}</p>
            {:else if isRecentRunsLoading && !recentRuns.length}
                <p class="muted">Loading persisted runs...</p>
            {:else if filteredRuns.length}
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Compare</th>
                                <th>Run ID</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th>Market</th>
                                <th>RMSE</th>
                                <th>Total Return</th>
                                <th>Eligibility</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each filteredRuns as run}
                                <tr>
                                    <td>
                                        <input
                                            type="checkbox"
                                            checked={selectedCompareIds.includes(
                                                run.run_id,
                                            )}
                                            onchange={(event) =>
                                                compareToggle(
                                                    run.run_id,
                                                    (
                                                        event.currentTarget as HTMLInputElement
                                                    ).checked,
                                                )}
                                        />
                                    </td>
                                    <td>{run.run_id}</td>
                                    <td>{run.status}</td>
                                    <td
                                        >{new Date(
                                            run.created_at,
                                        ).toLocaleString()}</td
                                    >
                                    <td>{run.market ?? "N/A"}</td>
                                    <td>
                                        {formatMetric(
                                            run.model_diagnostics?.rmse,
                                        )}
                                    </td>
                                    <td>
                                        {formatMetric(run.metrics?.total_return)}
                                    </td>
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
                <p class="muted">No persisted runs match the current filters.</p>
            {/if}
        </section>

        {#if comparisonRuns.length >= 2}
            <section class="surface">
                <div class="surface-header">
                    <div>
                        <p class="eyebrow">Comparison</p>
                        <h3>{comparisonRuns.length} selected runs</h3>
                    </div>
                    <span
                        class="status-pill"
                        class:status-pill--limited={comparisonAssessment.findings.some(
                            (finding) => finding.severity === "blocker",
                        )}
                    >
                        {comparisonAssessment.status}
                    </span>
                </div>
                <div class="comparison-summary">
                    {#if comparisonAssessment.findings.length}
                        {#each comparisonAssessment.findings as finding}
                            <div
                                class="comparison-finding"
                                class:comparison-finding--note={finding.severity ===
                                    "note"}
                            >
                                <strong>{finding.label}</strong>
                                <span>{finding.detail}</span>
                            </div>
                        {/each}
                    {:else}
                        <p class="muted">
                            Selected runs share dataset, target, cost basis, and
                            persisted result artifacts.
                        </p>
                    {/if}
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Run ID</th>
                                <th>Dataset</th>
                                <th>Target</th>
                                <th>Features</th>
                                <th>Model</th>
                                <th>Cost Basis</th>
                                <th>RMSE</th>
                                <th>Rank IC</th>
                                <th>Total Return</th>
                                <th>Baseline Delta</th>
                                <th>Caveat</th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each comparisonRuns as run}
                                {@const comparison = getComparisonFields(run)}
                                {@const baseline = summarizeBaselineComparison(run)}
                                <tr>
                                    <td>{run.run_id}</td>
                                    <td>{comparison.datasetLabel}</td>
                                    <td>{comparison.targetLabel}</td>
                                    <td>{comparison.featureLabel}</td>
                                    <td>{comparison.modelLabel}</td>
                                    <td>{comparison.costLabel}</td>
                                    <td>
                                        {formatMetric(
                                            run.model_diagnostics?.rmse,
                                        )}
                                    </td>
                                    <td>
                                        {formatMetric(
                                            run.model_diagnostics?.rank_ic,
                                        )}
                                    </td>
                                    <td>
                                        {formatMetric(run.metrics?.total_return)}
                                    </td>
                                    <td>{formatMetric(baseline?.delta)}</td>
                                    <td>{getComparableReason(run)}</td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            </section>
        {/if}

        {#if activeRunId}
            <section class="results-shell">
                <div class="surface">
                    <div class="surface-header">
                        <div>
                            <p class="eyebrow">Selected Result</p>
                            <h3>{activeRunId}</h3>
                        </div>
                        {#if isSelectedRunLoading}
                            <span class="muted">Loading...</span>
                        {/if}
                    </div>
                    {#if selectedRunError}
                        <p class="muted">{selectedRunError}</p>
                    {:else if activeRun?.metrics}
                        <ResearchRunMetrics metrics={activeRun.metrics} />
                    {:else}
                        <p class="muted">
                            Strategy metrics are unavailable for this record.
                        </p>
                    {/if}
                </div>

                <ResearchRunDiagnostics
                    diagnostics={activeRun?.model_diagnostics ?? null}
                />

                {#if activeRun?.equity_curve?.length}
                    <div class="surface">
                        <div class="surface-header">
                            <div>
                                <p class="eyebrow">Strategy Backtest</p>
                                <h3>Equity Curve</h3>
                            </div>
                        </div>
                        <EquityChart points={activeRun.equity_curve} />
                    </div>
                {:else}
                    <div class="surface">
                        <p class="muted">
                            Equity curve is unavailable for this record. This is
                            expected for older metadata-only runs.
                        </p>
                    </div>
                {/if}

                <ResearchRunValidation
                    validation={activeRun?.validation ?? null}
                    warnings={activeRun?.warnings ?? []}
                />

                {#if Object.keys(activeRun?.baselines ?? {}).length}
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
                                    {#each Object.entries(activeRun?.baselines ?? {}) as [baseline, metrics]}
                                        <tr>
                                            <td>{baseline}</td>
                                            <td>
                                                {formatMetric(
                                                    metrics.total_return,
                                                )}
                                            </td>
                                            <td>{formatMetric(metrics.sharpe)}</td>
                                            <td>
                                                {formatMetric(
                                                    metrics.max_drawdown,
                                                )}
                                            </td>
                                            <td>{formatMetric(metrics.turnover)}</td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    </div>
                {/if}

                {#if activeRun?.signals?.length}
                    <ResearchRunSignals signals={activeRun.signals} />
                {:else}
                    <div class="surface">
                        <p class="muted">
                            Signals are unavailable for this record. This is
                            expected for older metadata-only runs.
                        </p>
                    </div>
                {/if}
            </section>
        {:else}
            <section class="surface">
                <p class="muted">Submit or load a run to review results.</p>
            </section>
        {/if}

        <section class="surface">
            <div class="surface-header surface-header--stack">
                <div>
                    <p class="eyebrow">Readiness Context</p>
                    <h3>Capability state for this run</h3>
                </div>
                <p class="muted">
                    Hidden advanced modules remain diagnostic context only.
                    Current blocker count: {blockerCount}
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

        {#if metadataRun}
            <details class="surface advanced-surface">
                <summary>Advanced metadata</summary>
                <div class="metadata-grid">
                    <div>
                        <p class="eyebrow">Config Sources</p>
                        <pre>{stringifyJson(metadataRun.config_sources)}</pre>
                    </div>
                    <div>
                        <p class="eyebrow">Fallback Audit</p>
                        <pre>{stringifyJson(metadataRun.fallback_audit)}</pre>
                    </div>
                    <div>
                        <p class="eyebrow">Version Pack</p>
                        <pre>
{stringifyJson({
                                threshold_policy_version:
                                    metadataRun.threshold_policy_version,
                                price_basis_version:
                                    metadataRun.price_basis_version,
                                benchmark_comparability_gate:
                                    metadataRun.benchmark_comparability_gate,
                                comparison_eligibility:
                                    metadataRun.comparison_eligibility,
                                model_family: metadataRun.model_family,
                                training_output_contract_version:
                                    metadataRun.training_output_contract_version,
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
    .governance-grid,
    .registry-controls {
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

    .summary-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .governance-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .registry-controls {
        grid-template-columns: 1.4fr repeat(2, minmax(180px, 0.5fr));
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

    .status-pill {
        border-radius: 999px;
        border: 1px solid rgba(45, 212, 191, 0.32);
        color: #99f6e4;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.4rem 0.7rem;
        white-space: nowrap;
    }

    .status-pill--limited {
        border-color: rgba(251, 191, 36, 0.36);
        color: #fde68a;
    }

    .comparison-summary {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-bottom: var(--space-4);
    }

    .comparison-finding {
        display: grid;
        gap: 0.25rem;
        min-width: min(100%, 220px);
        padding: 0.8rem 0.9rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(251, 191, 36, 0.2);
        background: rgba(113, 63, 18, 0.18);
    }

    .comparison-finding--note {
        border-color: rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.6);
    }

    .comparison-finding strong {
        font-size: 0.82rem;
    }

    .comparison-finding span {
        color: var(--muted);
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .advanced-surface summary {
        cursor: pointer;
        font-weight: 600;
    }

    @media (max-width: 1200px) {
        .summary-grid,
        .governance-grid,
        .registry-controls {
            grid-template-columns: 1fr;
        }
    }
</style>
