---
status: proposed
date: 2026-08-10
legacy_id: TBD-PHASE-003
---

# A portfolio ledger closes the loop through manual adoption, not automation

**Proposed.** This is the project's later north star, not current work.

Today the product emits opinions and never learns whether they were useful. A
ledger would close that loop by recording which opinions the researcher actually
adopted, at what price, and how those positions performed against a baseline
after the opinion date.

The critical constraint is that this must **record** rather than **act**.
ADR-0018 draws the line: a ledger that knows real holdings is one small step
from sizing against them, and one more from acting on them. Manual adoption
tracking, forward-outcome comparison, and portfolio-impact reporting come first
and stand alone; automatic rebalancing or account control requires reversing
ADR-0018, which is a product-identity change.

## Conditions before acceptance

1. Manual adoption record fields defined — which opinion, which run, adopted
   when, at what price, with what intended horizon.
2. Forward-outcome comparison method defined, including the baseline an adopted
   opinion is measured against.
3. Portfolio-impact reporting specified without any order-generation surface.
4. An explicit statement that holdings data does not feed back into model input
   or position sizing.
