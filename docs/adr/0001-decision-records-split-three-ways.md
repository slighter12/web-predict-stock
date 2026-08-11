---
status: accepted
date: 2026-08-10
supersedes: docs/decision-register.md
supersedes_language: none
---

# Decision records are split three ways

`docs/decision-register.md` mixed three different kinds of information in one
file: settled decisions, open questions with no answer yet, and deferred
platform topics. At the same time the product identity itself lived in
`.codex/skills/quant-product-strategy-review/references/product-compass.md`,
which declared that it outranked `docs/`. Two files claimed authority over
scope and one file held three unrelated jobs.

(The `.codex/` tree is gone. What survived of that skill — its trigger
conditions, workflow, and anti-drift checks — is now
`docs/review-checklist.md`, which defers to the ADRs instead of outranking
them.)

We split decision information by whether a decision exists:

- `docs/adr/` — a decision **was made**. One file per decision, recording why.
- `docs/open-decisions.md` — a decision is **still missing** and has no
  direction yet. A flat list with owner area and acceptance trigger.
- `CONTEXT.md` — what a **term means**. Glossary only, no rules, no rationale.

A future decision with a known direction but no evidence to close it is an ADR
with `status: proposed`, not an open decision. An open decision is a policy gap
where even the direction is undecided.

## Consequences

- `docs/decision-register.md` is retired. Its entries are routed by ownership:
  cross-cutting rationale belongs in ADRs, strategic goals belong in
  `docs/project-goals.md`, delivery sequencing belongs in `docs/plan.md`,
  unresolved policy gaps belong in `docs/open-decisions.md`, and terminology
  belongs in `CONTEXT.md`. This is not a claim that every accepted register
  entry became an ADR.
- ADRs that were rewritten from a register entry carry a `legacy_id` field so
  `git log docs/` can be traced back.
- Product identity moved out of `.codex/` into ADR-0002, ADR-0003, and
  ADR-0004. What remained of that skill — its triggers, workflow, and drift
  checks — became `docs/review-checklist.md`, and `.codex/` was removed.

## Legacy destinations

The following retained register entries are checkable at their owning
documents:

- `DEC-V1-005` → [`docs/project-goals.md#v1-goal-table`](../project-goals.md#v1-goal-table), `G4 Model diagnostics before strategy claims`.
- `DEC-PHASE-003` → [`docs/plan.md#phase-2-sequencing`](../plan.md#phase-2-sequencing), `Phase 2 Sequencing`.
- `DEC-PHASE-009` → [`docs/plan.md#retired-retain-the-current-ui-dec-phase-009`](../plan.md#retired-retain-the-current-ui-dec-phase-009), the retirement entry in `docs/plan.md`.
