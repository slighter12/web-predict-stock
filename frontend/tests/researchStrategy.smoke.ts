import {
  describeEffectiveStrategy,
  getRunStrategyPresentation,
} from "../src/lib/state/strategy";
import type { EffectiveStrategy } from "../src/lib/types/runtime";
import type { ConfigValueSource } from "../src/lib/types/common";

const assert: (
  condition: unknown,
  message: string,
) => asserts condition = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const legacyStatic: EffectiveStrategy = {
  threshold: 0.003,
  top_n: 3,
};
const explicitStatic: EffectiveStrategy = {
  threshold: 0.004,
  top_n: 5,
  threshold_mode: "static",
  dynamic_threshold_policy: null,
};
const dynamic: EffectiveStrategy = {
  threshold: null,
  top_n: 5,
  threshold_mode: "dynamic",
  dynamic_threshold_policy: {
    policy_version: "volatility_scaled_positive_return_threshold_v2",
    return_target: "open_to_open",
    horizon_days: 20,
    lookback: 60,
    multiplier: 1.5,
    estimator: "sample_standard_deviation",
    ddof: 1,
    complete_window_required: true,
    continuity_policy_version: "market_date_continuity_v1",
    horizon_scaling: "square_root",
  },
};

const legacyPresentation = describeEffectiveStrategy(legacyStatic);
assert(legacyPresentation.label === "Static", "legacy static mode drifted");
assert(
  legacyPresentation.detail.includes("threshold 0.003"),
  "legacy threshold should remain visible",
);

const explicitPresentation = describeEffectiveStrategy(explicitStatic);
assert(
  explicitPresentation.detail.includes("threshold 0.004"),
  "explicit static threshold should remain visible",
);

const dynamicPresentation = describeEffectiveStrategy(dynamic);
assert(dynamicPresentation.label === "Dynamic", "dynamic mode drifted");
assert(
  dynamicPresentation.detail.includes("lookback 60") &&
    dynamicPresentation.detail.includes("multiplier 1.5") &&
    dynamicPresentation.detail.includes("policy volatility_scaled_positive_return_threshold_v2"),
  "dynamic policy details should remain visible",
);
assert(
  !dynamicPresentation.detail.includes("0%") &&
    !dynamicPresentation.detail.includes("N/A"),
  "dynamic thresholds must not be rendered as numeric placeholders",
);

const manifest = {
  candidate_id: "lineage-a-candidate",
  phase: "parameter_search",
  feature_set_id: "baseline",
  feature_families: ["trend", "volatility"],
  horizon_days: 20,
  model_type: "extra_trees",
  capacity_preset: "balanced",
  model_params: { n_estimators: 100 },
  volatility_lookback: 60,
  multiplier: 1.5,
  top_n: 5,
  threshold_policy_version: "volatility_scaled_positive_return_threshold_v2",
  direction_gate_policy_version: "direction_gate_v1",
  matched_baseline_policy_version: "matched_baseline_v1",
};
const firstRun = getRunStrategyPresentation({
  effective_strategy: dynamic,
  request_payload: {
    method_selection: { candidate_manifest: manifest },
  },
});
const secondRun = getRunStrategyPresentation({
  effective_strategy: dynamic,
  request_payload: {
    method_selection: {
      candidate_manifest: { ...manifest, candidate_id: "lineage-b-candidate" },
    },
  },
});
assert(
  firstRun.signature === secondRun.signature,
  "lineage identity must not change canonical strategy signature",
);

const changedPolicy: EffectiveStrategy = {
  ...dynamic,
  dynamic_threshold_policy: {
    ...dynamic.dynamic_threshold_policy,
    multiplier: 2,
  },
};
const changedRun = getRunStrategyPresentation({
  effective_strategy: changedPolicy,
  request_payload: {
    method_selection: { candidate_manifest: manifest },
  },
});
assert(
  firstRun.signature !== changedRun.signature,
  "dynamic policy changes must change comparison signature",
);

const missingPolicy = {
  threshold: null,
  top_n: 5,
  threshold_mode: "dynamic",
  dynamic_threshold_policy: null,
} as unknown as EffectiveStrategy;
const missingPolicyPresentation = getRunStrategyPresentation({
  effective_strategy: missingPolicy,
  request_payload: null,
});
assert(
  missingPolicyPresentation.missing &&
    missingPolicyPresentation.detail.includes("metadata is unavailable"),
  "incomplete dynamic metadata should remain visible as incomplete",
);

const derivedSource: ConfigValueSource = "derived_policy";
assert(derivedSource === "derived_policy", "derived policy source drifted");

console.log("research strategy smoke test passed");
