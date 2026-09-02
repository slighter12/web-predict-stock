import type { ResearchRunRecord } from "../types/researchRuns";
import type {
  DynamicEffectiveStrategy,
  EffectiveStrategy,
} from "../types/runtime";

export interface StrategyPresentation {
  label: string;
  detail: string;
  signature: string;
  missing: boolean;
}

type StrategyRun = Pick<ResearchRunRecord, "effective_strategy" | "request_payload">;

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
  JSON.stringify(normalizeForSignature(value)) ?? "";

const formatNumber = (value: number) =>
  Number.isFinite(value) ? String(value) : "invalid";

export const isDynamicEffectiveStrategy = (
  strategy: EffectiveStrategy | null | undefined,
): strategy is DynamicEffectiveStrategy =>
  strategy?.threshold_mode === "dynamic";

const dynamicPolicyTuple = (
  strategy: DynamicEffectiveStrategy,
) => ({
  policy_version: strategy.dynamic_threshold_policy.policy_version,
  return_target: strategy.dynamic_threshold_policy.return_target,
  horizon_days: strategy.dynamic_threshold_policy.horizon_days,
  lookback: strategy.dynamic_threshold_policy.lookback,
  multiplier: strategy.dynamic_threshold_policy.multiplier,
  estimator: strategy.dynamic_threshold_policy.estimator,
  ddof: strategy.dynamic_threshold_policy.ddof,
  complete_window_required:
    strategy.dynamic_threshold_policy.complete_window_required,
  continuity_policy_version:
    strategy.dynamic_threshold_policy.continuity_policy_version,
  horizon_scaling: strategy.dynamic_threshold_policy.horizon_scaling,
});

export const describeEffectiveStrategy = (
  strategy: EffectiveStrategy | null | undefined,
): StrategyPresentation => {
  if (!strategy) {
    return {
      label: "Strategy unavailable",
      detail: "No effective strategy metadata is available.",
      signature: "missing",
      missing: true,
    };
  }

  if (isDynamicEffectiveStrategy(strategy)) {
    const policy = strategy.dynamic_threshold_policy;
    if (!policy) {
      return {
        label: "Dynamic",
        detail: "Dynamic threshold policy metadata is unavailable.",
        signature: "dynamic:missing-policy",
        missing: true,
      };
    }
    return {
      label: "Dynamic",
      detail: `${policy.return_target} / ${policy.horizon_days}d · lookback ${policy.lookback} · multiplier ${formatNumber(policy.multiplier)} · policy ${policy.policy_version}`,
      signature: stableStringify({
        threshold_mode: "dynamic",
        top_n: strategy.top_n,
        policy: dynamicPolicyTuple(strategy),
      }),
      missing: false,
    };
  }

  return {
    label: "Static",
    detail: `threshold ${formatNumber(strategy.threshold)} · top N ${strategy.top_n}`,
    signature: stableStringify({
      threshold_mode: "static",
      threshold: strategy.threshold,
      top_n: strategy.top_n,
    }),
    missing: false,
  };
};

export const getPayloadObject = (
  payload: Record<string, unknown> | null | undefined,
  key: string,
) => {
  const value = payload?.[key];
  return isRecord(value) ? value : null;
};

const canonicalManifest = (
  payload: Record<string, unknown> | null | undefined,
) => {
  const methodSelection = getPayloadObject(payload, "method_selection");
  const manifest = getPayloadObject(methodSelection, "candidate_manifest");
  if (!manifest) {
    return null;
  }
  return Object.fromEntries(
    Object.entries(manifest).filter(
      ([key]) => key !== "candidate_id" && key !== "phase",
    ),
  );
};

export const getRunStrategyPresentation = (
  run: StrategyRun,
): StrategyPresentation => {
  const presentation = describeEffectiveStrategy(run.effective_strategy);
  if (
    !isDynamicEffectiveStrategy(run.effective_strategy) ||
    presentation.missing
  ) {
    return presentation;
  }

  return {
    ...presentation,
    signature: stableStringify({
      threshold_mode: "dynamic",
      top_n: run.effective_strategy.top_n,
      policy: dynamicPolicyTuple(run.effective_strategy),
      canonical_manifest: canonicalManifest(run.request_payload),
    }),
  };
};
