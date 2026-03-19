<script lang="ts">
    import { createMutation, createQuery } from "@tanstack/svelte-query";

    import {
        ApiError,
        createResearchRun,
        fetchResearchRun,
        fetchSystemHealth,
    } from "../api";
    import type {
        AppError,
        HealthResponse,
        ResearchRunCreateRequest,
        ResearchRunRecord,
        ResearchRunResponse,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
    import DataIngestionPanel from "./data-plane/DataIngestionPanel.svelte";
    import ImportantEventPanel from "./data-plane/ImportantEventPanel.svelte";
    import LifecyclePanel from "./data-plane/LifecyclePanel.svelte";
    import RecoveryDrillPanel from "./data-plane/RecoveryDrillPanel.svelte";
    import ReplayPanel from "./data-plane/ReplayPanel.svelte";
    import ResearchRunForm from "./research-runs/ResearchRunForm.svelte";
    import ResearchRunInspector from "./research-runs/ResearchRunInspector.svelte";

    let latestResult: ResearchRunResponse | null = null;
    let submitError: AppError | null = null;
    let researchRunRecord: ResearchRunRecord | null = null;
    let recordError: string | null = null;
    let runLookupId = "";
    let isRunLoading = false;
    let inspectorRunState: {
        result: ResearchRunResponse | null;
        isSubmitting: boolean;
        error: AppError | null;
    };
    let inspectorRegistryState: {
        researchRunRecord: ResearchRunRecord | null;
        recordError: string | null;
        isRunLoading: boolean;
        runLookupId: string;
        onRunLookup: (runId: string) => void;
    };
    let inspectorHealthState: {
        health: HealthResponse | null;
        isHealthLoading: boolean;
        healthError: string | null;
    };

    const loadResearchRun = async (runId: string) => {
        if (!runId.trim()) {
            researchRunRecord = null;
            recordError = null;
            return;
        }

        isRunLoading = true;
        try {
            researchRunRecord = await fetchResearchRun(runId.trim());
            recordError = null;
        } catch (error) {
            researchRunRecord = null;
            if (error instanceof ApiError) {
                recordError = `${error.code}: ${error.message}`;
            } else {
                recordError = "Unable to load research run details.";
            }
        } finally {
            isRunLoading = false;
        }
    };

    const healthQuery = createQuery({
        queryKey: ["system", "health"],
        queryFn: fetchSystemHealth,
        retry: false,
        refetchOnWindowFocus: false,
    });

    const researchRunMutation = createMutation({
        mutationFn: createResearchRun,
        onSuccess: (data) => {
            latestResult = data;
            submitError = null;
            runLookupId = data.run_id;
            void loadResearchRun(data.run_id);
        },
        onError: (error) => {
            latestResult = null;
            if (error instanceof ApiError) {
                submitError = error;
                return;
            }

            submitError = {
                status: 0,
                code: "NETWORK_ERROR",
                message:
                    "Unable to reach the backend. Check VITE_API_BASE_URL and backend status.",
                requestId: null,
            };
        },
    });

    const handleSubmit = (payload: ResearchRunCreateRequest) => {
        submitError = null;
        $researchRunMutation.mutate(payload);
    };

    const handleRunLookup = (runId: string) => {
        runLookupId = runId;
        void loadResearchRun(runId);
    };

    $: inspectorRunState = {
        result: latestResult,
        isSubmitting: $researchRunMutation.isPending,
        error: submitError,
    };

    $: inspectorRegistryState = {
        researchRunRecord,
        recordError,
        isRunLoading,
        runLookupId,
        onRunLookup: handleRunLookup,
    };

    $: inspectorHealthState = {
        health: $healthQuery.data ?? null,
        isHealthLoading: $healthQuery.isPending,
        healthError:
            $healthQuery.error instanceof Error
                ? $healthQuery.error.message
                : null,
    };
</script>

<div class="dashboard-grid">
    <WorkspaceSection eyebrow="Research Runs" title="Research Run Workspace">
        <div class="research-grid">
            <ResearchRunForm
                isSubmitting={$researchRunMutation.isPending}
                onSubmit={handleSubmit}
            />
            <ResearchRunInspector
                runState={inspectorRunState}
                registryState={inspectorRegistryState}
                healthState={inspectorHealthState}
            />
        </div>
    </WorkspaceSection>

    <WorkspaceSection eyebrow="Data Plane" title="Data Plane Workspace">
        <div class="data-grid">
            <DataIngestionPanel />
            <ReplayPanel />
            <RecoveryDrillPanel />
            <LifecyclePanel />
            <ImportantEventPanel />
        </div>
    </WorkspaceSection>
</div>

<style>
    .dashboard-grid {
        display: grid;
        gap: 1.2rem;
    }

    .research-grid {
        display: grid;
        grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
        gap: 1.2rem;
        align-items: start;
    }

    .data-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
    }

    @media (max-width: 1100px) {
        .research-grid,
        .data-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
