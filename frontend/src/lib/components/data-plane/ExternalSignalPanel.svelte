<script lang="ts">
    import { onMount } from "svelte";

    import {
        ApiError,
        createExternalSignalAudit,
        createExternalSignalIngestion,
        createFactorCatalog,
        fetchExternalSignalAudits,
        fetchExternalSignals,
        fetchFactorCatalogs,
        fetchFactorMaterializations,
    } from "../../api";
    import type {
        ExternalSignalAuditRecord,
        ExternalSignalRecord,
        FactorCatalogRecord,
        FactorMaterializationRecord,
    } from "../../types";

    let ingestionForm = {
        market: "TW",
        source_family: "tw_company_event_layer_v1",
        coverage_start: "2024-01-01",
        coverage_end: "2024-12-31",
    };
    let auditForm = {
        market: "TW",
        source_family: "tw_company_event_layer_v1",
        audit_window_start: "2024-01-01",
        audit_window_end: "2024-12-31",
    };
    let catalogId = "p7_factor_catalog_v1";
    let signals: ExternalSignalRecord[] = [];
    let audits: ExternalSignalAuditRecord[] = [];
    let catalogs: FactorCatalogRecord[] = [];
    let materializations: FactorMaterializationRecord[] = [];
    let errorMessage: string | null = null;

    const refresh = async () => {
        try {
            [signals, audits, catalogs, materializations] = await Promise.all([
                fetchExternalSignals(),
                fetchExternalSignalAudits(),
                fetchFactorCatalogs(),
                fetchFactorMaterializations(),
            ]);
            errorMessage = null;
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to load external-signal records.";
        }
    };

    const submitIngestion = async () => {
        try {
            await createExternalSignalIngestion(ingestionForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create external-signal ingestion.";
        }
    };

    const submitAudit = async () => {
        try {
            await createExternalSignalAudit(auditForm);
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create external-signal audit.";
        }
    };

    const submitCatalog = async () => {
        try {
            await createFactorCatalog({
                id: catalogId,
                market: "TW",
                source_family: "tw_company_event_layer_v1",
                lineage_version: "tw_company_event_lineage_v1",
                minimum_coverage_ratio: 0.8,
                is_active: true,
                entries: [
                    {
                        factor_id: "company_listing_age_days_v1",
                        display_name: "Company Listing Age Days",
                        formula_definition: "trading_date - listing_date",
                        lineage: "tw_company_event_lineage_v1",
                        timing_semantics: "fallback_listing_date_pti",
                        missing_value_policy: "null_when_listing_date_unknown",
                        scoring_eligible: true,
                    },
                    {
                        factor_id: "important_event_count_30d_v1",
                        display_name: "Important Event Count 30d",
                        formula_definition:
                            "count(important_events publication_ts in trailing 30d)",
                        lineage: "tw_company_event_lineage_v1",
                        timing_semantics: "official_publication_ts_pti",
                        missing_value_policy: "zero_when_no_events",
                        scoring_eligible: true,
                    },
                    {
                        factor_id: "lifecycle_transition_count_365d_v1",
                        display_name: "Lifecycle Transition Count 365d",
                        formula_definition:
                            "count(lifecycle effective_date in trailing 365d)",
                        lineage: "tw_company_event_lineage_v1",
                        timing_semantics: "effective_date_fallback_pti",
                        missing_value_policy: "zero_when_no_transitions",
                        scoring_eligible: true,
                    },
                ],
            });
            await refresh();
        } catch (error) {
            errorMessage =
                error instanceof ApiError
                    ? `${error.code}: ${error.message}`
                    : "Unable to create factor catalog.";
        }
    };

    onMount(() => {
        void refresh();
    });
</script>

<div class="surface">
    <div class="surface-header">
        <div>
            <p class="eyebrow">Data Plane</p>
            <h3>External Signals And Factor Catalog</h3>
        </div>
        <button type="button" onclick={refresh}>Refresh</button>
    </div>

    <div class="form-grid">
        <label
            ><span>Coverage Start</span><input
                type="date"
                bind:value={ingestionForm.coverage_start}
            /></label
        >
        <label
            ><span>Coverage End</span><input
                type="date"
                bind:value={ingestionForm.coverage_end}
            /></label
        >
        <label class="wide"
            ><span>Catalog ID</span><input bind:value={catalogId} /></label
        >
    </div>

    <div class="button-row">
        <button type="button" onclick={submitIngestion}
            >Build External Archive</button
        >
        <button type="button" onclick={submitAudit}>Run Audit</button>
        <button type="button" onclick={submitCatalog}>Seed Catalog</button>
    </div>
    {#if errorMessage}<p class="muted">{errorMessage}</p>{/if}

    <div class="list">
        <div class="row">
            <strong>Signals</strong><span>{signals.length}</span>
        </div>
        <div class="row">
            <strong>Audits</strong><span>{audits.length}</span>
        </div>
        <div class="row">
            <strong>Catalogs</strong><span>{catalogs.length}</span>
        </div>
        <div class="row">
            <strong>Materializations</strong><span
                >{materializations.length}</span
            >
        </div>
    </div>
</div>

<style>
    .surface,
    .form-grid,
    .list {
        display: grid;
        gap: 0.9rem;
    }
    .surface {
        padding: 1.1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.62);
    }
    .surface-header,
    .row,
    .button-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
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
    .form-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .wide {
        grid-column: 1 / -1;
    }
    label {
        display: grid;
        gap: 0.35rem;
    }
    span,
    .muted {
        color: var(--muted);
    }
    input,
    button {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        background: rgba(2, 6, 23, 0.72);
        color: var(--text);
    }
    .row {
        padding: 0.75rem 0.9rem;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.72);
    }
    @media (max-width: 720px) {
        .form-grid,
        .button-row {
            grid-template-columns: 1fr;
            display: grid;
        }
    }
</style>
