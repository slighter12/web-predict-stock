---
status: accepted
date: 2026-08-14
scope: TW daily
---

# Technical research trains a pooled cross-sectional model before Cluster-specific models

Method Candidate evaluation will train one Pooled Cross-Sectional Model from
the TW daily Model-Ready Universe instead of fitting an independent model for
each Symbol. This better matches the intended progression: a shared initial
model, followed later by Cluster-specific models that use the same evaluation
contract on explicitly defined subsets.

All Fold boundaries are Market-Date boundaries: no rows for one Market Date may
appear in both a Fold's training and Holdout partitions. The current-active
membership caveat remains applicable until point-in-time membership history is
available; it is not removed by pooling.

## Considered Options

- Per-Symbol models were rejected for Method Candidate selection because each
  Symbol has far fewer daily observations, and their separate fits do not form
  a natural foundation for later Cluster-specific models.
- Cluster-specific models are deferred until a Cluster policy is separately
  defined and evaluated; using undeclared clusters now would hide a second
  source of selection bias.

## Consequences

- The present per-Symbol training flow must not be reused for this research
  path.
- Method Candidate, Fold, diagnostic, and persisted-artifact contracts must
  identify the pooled evaluation set and its date boundaries.
