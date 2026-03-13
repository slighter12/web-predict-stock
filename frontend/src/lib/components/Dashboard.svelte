<script lang="ts">
  import { createMutation, createQuery } from "@tanstack/svelte-query";

  import BacktestForm from "./BacktestForm.svelte";
  import ResultsPanel from "./ResultsPanel.svelte";
  import { ApiError, fetchHealth, runBacktest } from "../api";
  import type { AppError, BacktestRequest, BacktestResponse } from "../types";

  let latestResult: BacktestResponse | null = null;
  let submitError: AppError | null = null;

  const healthQuery = createQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const backtestMutation = createMutation({
    mutationFn: runBacktest,
    onSuccess: (data) => {
      latestResult = data;
      submitError = null;
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
        message: "Unable to reach the backend. Check VITE_API_BASE_URL and backend status.",
        requestId: null,
      };
    },
  });

  const handleSubmit = (payload: BacktestRequest) => {
    submitError = null;
    $backtestMutation.mutate(payload);
  };
</script>

<div class="dashboard-shell">
  <BacktestForm isSubmitting={$backtestMutation.isPending} onSubmit={handleSubmit} />
  <ResultsPanel
    result={latestResult}
    isSubmitting={$backtestMutation.isPending}
    error={submitError}
    health={$healthQuery.data ?? null}
    isHealthLoading={$healthQuery.isPending}
    healthError={$healthQuery.error instanceof Error ? $healthQuery.error.message : null}
  />
</div>

<style>
  .dashboard-shell {
    display: grid;
    grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
    gap: 1.2rem;
    align-items: start;
  }

  @media (max-width: 1100px) {
    .dashboard-shell {
      grid-template-columns: 1fr;
    }
  }
</style>
