---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-013
scope: TW daily
---

# Unauthenticated company crawls may add only trusted current listings and never deactivate profiles

Company-profile reconciliation — deciding that a symbol has left the active
universe — is an **internal ingestion operation**. Local scripts and internal
ingestion may reconcile; the unauthenticated company-crawl HTTP endpoint may
fetch and upsert profiles, but must never mark missing profiles inactive.

Additive writes have a separate trust boundary. They are accepted only from the
fixed TWSE and TPEX current-listing feeds. Membership in one of those feeds is
the evidence that a profile is currently active; the feeds do not publish a
record-level trading-status field. Configurable or redirected URLs, mismatched
source metadata, and records that explicitly declare an inactive or unknown
status are rejected rather than added to the current-active universe.

The asymmetry is deliberate and is enforced in code:
`backend/market_data/api.py` pins `reconcile=False` at the HTTP boundary, and
internal reconciliation additionally refuses to run when the crawled feed covers
too small a fraction of the currently active set
(`backend/market_data/services/company_crawlers.py`).

The failure mode is what makes this worth recording. Adding a profile that turns
out to be wrong costs one bad row. Deactivating profiles in bulk removes symbols
from the ingestion universe (ADR-0012), which stops their daily data being
collected — and under ADR-0012 that history, once not collected, cannot be
recovered later. One truncated or malformed crawl reaching an unauthenticated
endpoint could therefore do permanent, silent damage to the dataset. Additive
operations are recoverable; subtractive ones are not.

## Consequences

- Reconciliation cannot be triggered by anyone who can reach the HTTP surface,
  which is the point: the endpoint is unauthenticated.
- The company-profile source URLs are not deployment overrides. Supporting a
  different provider requires a separate trusted-source decision and parser
  contract rather than relabeling its response with an allowlisted source name.
- This is a stopgap tied to the absence of an authenticated API boundary. If one
  is introduced, the restriction can be revisited — but the coverage-ratio guard
  should survive that change on its own merits.
- The coverage-ratio constant guarding internal reconciliation is currently an
  unversioned literal, which ADR-0004 does not permit; see `OPEN-011`.
