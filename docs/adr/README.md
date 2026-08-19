# Architecture Decision Records

One file per accepted decision or proposed direction. Decisions still missing
live in [`../open-decisions.md`](../open-decisions.md); term definitions live
in [`../../CONTEXT.md`](../../CONTEXT.md). The split is explained in ADR-0001.

`status: proposed` means the direction is known but the evidence to close it is
not; it does not authorize implementation. `status: accepted` means the
decision is in force.

Numbering is sequential and never reused. New ADRs continue at 0024.

A `scope:` field in an ADR's frontmatter marks the decision as specific to one
market lane. Its absence means the decision applies repository-wide.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-decision-records-split-three-ways.md) | Decision records are split three ways | accepted |
| [0002](0002-research-to-opinion-workbench-boundary.md) | The product is a research-to-opinion workbench, not a broker or an advisor | accepted |
| [0003](0003-market-phased-tw-daily-first.md) | Market-phased: TW daily first, contracts stay market-agnostic | accepted |
| [0004](0004-no-invented-thresholds.md) | Thresholds are provisional-and-labeled or versioned-and-explainable | accepted |
| [0005](0005-long-only-direction-gate-magnitude-ranking.md) | Long-only makes direction an admission gate and magnitude the ranking | accepted |
| [0006](0006-bounded-contexts-with-enforced-layering.md) | Bounded contexts with inward layering, enforced by tests | accepted |
| [0007](0007-single-timescaledb-store.md) | One TimescaleDB instance holds everything | accepted |
| [0008](0008-local-tabular-ml-extra-trees-default.md) | Local tabular tree ensembles, defaulting to Extra Trees | accepted |
| [0009](0009-vectorbt-backtest-external-frameworks-as-reference.md) | vectorbt runs the backtest; external frameworks are reference material | accepted |
| [0010](0010-single-repo-fastapi-monolith-svelte-spa.md) | One repository, one FastAPI backend, one Svelte SPA | accepted |
| [0011](0011-preserve-raw-provider-payloads.md) | TW daily ingestion preserves raw payloads and stays rebuildable | accepted |
| [0012](0012-tw-company-profiles-current-active-universe.md) | The TW universe is a current-active selection filter, with no status history | accepted |
| [0013](0013-fail-closed-tw-no-data-detection.md) | TW daily no-data detection fails closed | accepted |
| [0014](0014-readiness-denominator-requested-symbol-coverage.md) | Readiness is measured against requested symbols over known market dates | accepted |
| [0015](0015-persisted-runs-fully-reviewable-derived-completeness.md) | A persisted run reloads as completely as it ran; completeness is derived | accepted |
| [0016](0016-opinion-artifact-deterministic-reconstruction.md) | The opinion artifact is reconstructed deterministically from run artifacts | accepted |
| [0017](0017-advanced-modules-as-internal-foundations.md) | Platform-era modules are internal foundations, not product surfaces | accepted |
| [0018](0018-no-broker-execution.md) | No broker execution, no live orders, no portfolio auto-control | accepted |
| [0019](0019-market-sentiment-feature-family.md) | Sentiment Feature Family feeds existing Prediction Tasks | proposed |
| [0020](0020-value-fundamental-research-track.md) | Fundamental Research Track complements the Technical Research Track | proposed |
| [0021](0021-us-daily-expansion.md) | US daily is the second market lane | proposed |
| [0022](0022-portfolio-ledger-manual-adoption.md) | A portfolio ledger closes the loop through manual adoption, not automation | proposed |
| [0023](0023-company-profile-reconciliation-trust-boundary.md) | Unauthenticated company crawls may add only trusted current listings and never deactivate profiles | accepted |
| [0024](0024-volatility-scaled-positive-return-threshold.md) | Direction Gate labels use a volatility-scaled Positive Return Threshold | accepted |
| [0025](0025-pooled-cross-sectional-model-before-clusters.md) | Technical research trains a pooled cross-sectional model before Cluster-specific models | accepted |
| [0026](0026-method-selection-matrix-summary-boundary.md) | Method Selection Matrices retain candidate summaries; shortlisted results are complete Research Runs | accepted |

## Writing a new one

Keep it short. State the context, the decision, and why, in a few sentences.
Add `Considered Options` only when a rejected alternative is worth remembering,
and `Consequences` only when a downstream effect is non-obvious.

Write an ADR when all three hold: the decision is hard to reverse, a future
reader would otherwise wonder why the code looks like this, and there was a real
alternative. If any one is missing, it is not an ADR.
