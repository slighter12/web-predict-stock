---
name: quant-product-strategy-review
description: "Review product direction for this quant research-to-opinion workbench. Use when the user asks for roadmap, phase planning, product direction, scope review, next-stage prioritization, CEO/PM review, or docs drift. Avoid for ordinary implementation, bugfixes, tests, commits, or code review unless product strategy is explicitly in scope."
compatibility: [codex, claude, gemini]
metadata:
  version: "0.1.1"
---

# Quant Product Strategy Review

## Purpose

Keep product planning anchored on a CEO/PM view of the workbench: convert quant
research artifacts into decision-useful model opinions without drifting back
into maintenance-only hardening or jumping prematurely into broker/live
execution.

This is a project-local strategy skill. It interprets long repository docs
through the product compass before proposing roadmap, phase, or scope decisions.

## Use When

- The user asks for product direction, product strategy, roadmap, phase
  planning, or next-stage prioritization.
- The user asks whether the project, docs, or a proposed feature is drifting.
- The user asks for a CEO/PM-style review of this repository.
- The task is to choose between product directions or define a Phase proposal.

## Avoid When

- The task is a normal implementation, bugfix, test, commit, or code review.
- The user only asks for a focused engineering change with stable requirements.
- A narrower skill owns the work, such as `change-sanity-review` for current
  diffs or `conventional-git-flow` for commits and PRs.

## Workflow

1. Load `references/product-compass.md` first.
2. Inspect only the project docs needed to verify the specific question. Treat
   README, goals, specs, plans, status, gates, and decision docs as evidence,
   not as a fresh source of product identity on every turn.
3. State the active product frame as defined in
   `references/product-compass.md` before recommending work. Do not restate or
   maintain a second product-frame definition in this file.
4. Challenge the proposal with the anti-drift checks defined in
   `references/product-compass.md` before giving a plan.
5. If logic is not closed, ask targeted questions before proposing a phase or
   PR sequence. If a reasonable assumption is safe, state it explicitly.
6. When proposing work, require the output to describe product value,
   decision-usefulness value, scope risk, minimum PR shape, and manual
   verification.
7. If existing docs conflict with the product compass, flag the docs drift and
   name the docs that should be updated. Do not silently override docs or let
   conservative v1 wording erase the product direction.

## Tool And Side-Effect Boundaries

- Prefer read-only inspection for strategy review.
- Do not edit files unless the user explicitly asks for implementation.
- Do not propose new dependencies, DB migrations, broker execution, live-order
  semantics, or platform-control surfaces unless the user explicitly changes
  the product direction.
- Do not invent stable numeric thresholds for model quality, confidence, risk,
  or investability. Prototype thresholds must be labeled as provisional and
  later replaced by versioned policy.
- Do not turn model opinions into personalized investment advice. The product
  boundary is model opinion with manual adoption.

## Output

For product strategy requests, return:

- `understanding`: current product frame and the user's goal.
- `challenge`: contradictions, missing decisions, and anti-drift findings.
- `recommendation`: the recommended direction and why alternatives are weaker.
- `phase_or_pr_plan`: phase proposal or minimum PR slices when the logic is
  closed.
- `manual_verification`: checklist focused on product decision value.

## Version History

- v0.1.1 (2026-05-18): Make the product compass the single source of truth for
  the active product frame and anti-drift checks.
- v0.1.0 (2026-05-18): Initial project-local CEO/PM strategy review skill.

## References

- `references/product-compass.md` - Product identity, phase direction,
  boundaries, anti-drift checks, and output expectations.
