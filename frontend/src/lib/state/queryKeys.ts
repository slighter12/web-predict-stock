export const queryKeys = {
  systemHealth: ["system", "health"] as const,
  researchRuns: ["research-runs"] as const,
  researchRun: (runId: string) => ["research-runs", runId] as const,
  replays: ["data-plane", "replays"] as const,
  recoveryDrills: ["data-plane", "recovery-drills"] as const,
  lifecycleRecords: ["data-plane", "lifecycle-records"] as const,
  importantEvents: ["data-plane", "important-events"] as const,
};
