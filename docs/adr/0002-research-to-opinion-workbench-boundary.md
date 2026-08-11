---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-001
---

# The product is a research-to-opinion workbench, not a broker or an advisor

This project could plausibly grow in three directions: a research artifact
viewer, an automated trading system, or a personalized advisory product. We
chose a fourth, narrower position: a workbench that turns persisted quantitative
research artifacts into **model opinions** that a solo investor-researcher reads
before making their own decision.

The boundary is deliberate and has three parts:

- **Model opinion, not personalized investment advice.** Output describes what
  the model thinks about symbols, not what this particular person should do
  given their situation.
- **Manual adoption, not broker instruction.** The system never places, sizes,
  or routes an order. Adoption is a human act outside the system.
- **Next-session planning from daily data, not intraday execution judgment.**

When evidence is insufficient, the system must be allowed to emit `no-opinion`
or `do-not-adopt`. Forcing a buy list out of weak evidence is the specific
failure mode this boundary exists to prevent.

## Consequences

- Direct action-language labels (buy candidate, sell/avoid, watch) are allowed,
  because the boundary is about who decides, not about vocabulary softness.
- Every opinion needs an invalidation note saying when it should not be adopted.
- Success is measured as decision usefulness first, with forward outcome versus
  baseline as later validation — not as strategy return.
