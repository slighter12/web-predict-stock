---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-006, DEC-PHASE-007
---

# The opinion artifact is reconstructed deterministically from persisted run artifacts

`opinion_artifact` serializes opinion state, action rows, source references, and
review checks. It has one construction rule with two entry points:

- On `POST`, it is built from the current response artifacts.
- On detail reload, it is **reconstructed from the persisted run artifacts** —
  not restored from a separately stored copy.
- List responses stay summary-only and must never expose action rows or prose
  derived from heavy artifacts that were omitted from the response.

Storing the opinion as its own frozen blob was the alternative. Reconstruction
was chosen because it makes the opinion provably a function of the evidence: an
opinion that cannot be rederived from the run's artifacts is an opinion whose
basis has been lost, and it would be impossible to tell whether a stored
opinion still matches the data it claims to summarize.

## Consequences

- Every opinion field must be computable from persisted artifacts. A method that
  needs inputs the run never stored returns `not_evaluated` with a concrete
  reason — it does not invent data.
- Review checks must evaluate actual row fields and references. A check that
  passes merely because a row or an object exists is a defect.
- Row-level evidence, risk, and invalidation must be row-specific. Shared
  boilerplate across rows does not satisfy the contract.
- The list/detail boundary is a safety property, not an optimization.
