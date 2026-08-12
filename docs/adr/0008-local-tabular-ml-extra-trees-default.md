---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-010, TBD-004
---

# Models are local tabular tree ensembles, defaulting to Extra Trees

The modeling stack is scikit-learn tree ensembles running in-process. The
baseline builder defaults to **Extra Trees**, with XGBoost and Random Forest as
selectable variants. No deep learning, no GPU dependency, no external training
service.

Extra Trees is the default specifically so the common local research loop does
not require a working XGBoost native runtime. XGBoost remains the stronger
gradient-boosting option and stays selectable, but making it mandatory would put
a native-library installation between a researcher and their first research
run.

Tree ensembles over tabular technical features are also the honest baseline for
this data volume. A sequence model on daily TW equity data would add
architecture-tuning surface without a corresponding evidence gain, and the
project's priority order puts data readiness and reproducibility above model
novelty.

All supported model families use the same accepted complete-case input policy:
rows with any non-finite model input are removed before training or prediction.
Runs record `missing_feature_policy_version="complete_case_model_inputs_v1"`
and `missing_feature_policy_state="complete_case_applied"` so this behavior is
comparable after reload. The previous XGBoost-named metadata remains readable
on legacy payloads and is migrated without changing their recorded model family.
Migration 0009 normalizes that metadata one way: after the old value is replaced,
the database cannot infer which rows originally carried it, so downgrade refuses
to fabricate legacy provenance.

## Consequences

- Feature engineering carries the modeling burden, not architecture search.
- Feature importance is available cheaply and is a required diagnostic.
- Missing-feature handling is shared across Extra Trees, XGBoost, and Random
  Forest rather than varying silently by model implementation.
