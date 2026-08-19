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

## Consequences

- A Method Selection Matrix has its own retrieval and comparison contract.
- Candidate summaries must be sufficient to reproduce the selection decision;
  silently omitted rejected candidates are not allowed.
- The final per-Horizon shortlist contains at most three Method Candidates and
  produces complete Research Runs before it can generate Prospective Opinions.
