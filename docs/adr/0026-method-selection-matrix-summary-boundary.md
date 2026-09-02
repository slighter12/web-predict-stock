---
status: accepted
date: 2026-08-14
scope: TW daily
---

# Method Selection Matrices retain candidate summaries; shortlisted results are complete Research Runs

Nested Method Candidate evaluation can produce a large matrix of Feature,
model, threshold, strategy, and Fold combinations. The system will persist that
matrix as a Method Selection Matrix containing the reproducible candidate
manifest, Fold boundaries, summaries, ranking, and rejection reasons. It will
persist full artifacts only for the shortlisted and final-Holdout Research Runs.

This preserves selection traceability without falsely calling a partial inner
candidate a Research Run. It keeps ADR-0015 intact: any persisted Research Run
still reloads with every artifact required for review.

The final Holdout is the exact last 252 official signal Market Dates inside the
requested range. An official post-range Market-Date buffer is allowed only to
mature `open_to_open` labels and is excluded from all selection and refitting.
Before the final refit, each shortlist lineage searches the complete final
catalog independently. Internal deterministic reuse is allowed for resource
control, but lineage records and promoted Research Runs are never deduplicated.
Identical configurations receive a canonical configuration group and must be
treated as non-independent evidence by downstream comparisons.

Promotion is prepared in memory. Candidate-level artifact failures are retained
as `not_evaluated` results, while successful Research Runs and the Matrix are
committed atomically. A persistence failure must leave neither the Matrix nor
any of its promoted Runs committed.

## Consequences

- A Method Selection Matrix has its own retrieval and comparison contract.
- Candidate summaries must be sufficient to reproduce the selection decision;
  silently omitted rejected candidates are not allowed.
- The final per-Horizon shortlist contains at most three Method Candidates and
  produces complete Research Runs before it can generate Prospective Opinions.
- Dynamic promoted strategies persist their threshold policy metadata; a
  numeric placeholder is not a valid effective threshold and generic runtime
  replay does not infer one.
