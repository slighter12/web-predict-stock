---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-010
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

## Consequences

- Feature engineering carries the modeling burden, not architecture search.
- Feature importance is available cheaply and is a required diagnostic.
- A cross-model policy for missing features does not exist yet and stays an open
  decision; it only becomes urgent if model families widen.
