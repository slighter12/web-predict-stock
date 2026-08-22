import {
  FALLBACK_FEATURE_DEFINITIONS,
  FEATURE_REGISTRY_VERSION,
} from "../src/lib/state/featureRegistry";

console.log(
  JSON.stringify({
    version: FEATURE_REGISTRY_VERSION,
    features: FALLBACK_FEATURE_DEFINITIONS,
  }),
);
