<script lang="ts">
    import { createMutation, createQuery } from "@tanstack/svelte-query";

    import {
        ApiError,
        createResearchRun,
        fetchResearchGate,
        fetchResearchRun,
        fetchSystemHealth,
    } from "../api";
    import type {
        AppError,
        HealthResponse,
        ResearchPhaseGateResponse,
        ResearchRunCreateRequest,
        ResearchRunRecord,
        ResearchRunResponse,
    } from "../types";
    import WorkspaceSection from "./layout/WorkspaceSection.svelte";
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
    let inspectorGateState: {
        gates: ResearchPhaseGateResponse[];
        gateError: string | null;
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

    const p7GateQuery = createQuery({
        queryKey: ["research", "gate", "p7"],
        queryFn: () => fetchResearchGate("p7"),
        retry: false,
        refetchOnWindowFocus: false,
    });

    const p8GateQuery = createQuery({
        queryKey: ["research", "gate", "p8"],
        queryFn: () => fetchResearchGate("p8"),
        retry: false,
        refetchOnWindowFocus: false,
    });

    const p9GateQuery = createQuery({
        queryKey: ["research", "gate", "p9"],
        queryFn: () => fetchResearchGate("p9"),
        retry: false,
        refetchOnWindowFocus: false,
    });

    const p10GateQuery = createQuery({
        queryKey: ["research", "gate", "p10"],
        queryFn: () => fetchResearchGate("p10"),
        retry: false,
        refetchOnWindowFocus: false,
    });

    const p11GateQuery = createQuery({
        queryKey: ["research", "gate", "p11"],
        queryFn: () => fetchResearchGate("p11"),
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

    $: inspectorGateState = {
        gates: [
            $p7GateQuery.data,
            $p8GateQuery.data,
            $p9GateQuery.data,
            $p10GateQuery.data,
            $p11GateQuery.data,
        ].filter(Boolean) as ResearchPhaseGateResponse[],
        gateError:
            [
                $p7GateQuery.error,
                $p8GateQuery.error,
                $p9GateQuery.error,
                $p10GateQuery.error,
                $p11GateQuery.error,
            ].find((item) => item instanceof Error) instanceof Error
                ? (
                      [
                          $p7GateQuery.error,
                          $p8GateQuery.error,
                          $p9GateQuery.error,
                          $p10GateQuery.error,
                          $p11GateQuery.error,
                      ].find((item) => item instanceof Error) as Error
                  ).message
                : null,
    };
</script>

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
            gateState={inspectorGateState}
        />
    </div>
</WorkspaceSection>

<style>
    .research-grid {
        display: grid;
        grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
        gap: 1.2rem;
        align-items: start;
    }

    @media (max-width: 1100px) {
        .research-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
