# Product Review Checklist

A review procedure for product-direction work on this workbench. It is a
**workflow aid, not a source of truth**.

What the product is, where its boundaries are, and how thresholds are governed
are **decisions**, and decisions live in `docs/adr/`. This checklist descends
from a project-local agent skill that once carried those definitions and
asserted it outranked `docs/`. It no longer does either. When this file and an
ADR disagree, the ADR wins; if the ADR is wrong, change the ADR.

## Purpose

Keep product planning anchored on a CEO/PM view of the workbench: convert quant
research artifacts into decision-useful model opinions, without drifting back
into maintenance-only hardening or jumping prematurely into broker/live
execution.

## Use when

- Someone asks for product direction, strategy, roadmap, phase planning, or
  next-stage prioritization.
- Someone asks whether the project, its docs, or a proposed feature is drifting.
- Someone asks for a CEO/PM-style review of this repository.
- The task is to choose between product directions or define a phase proposal.

## Avoid when

- The task is ordinary implementation, a bugfix, a test, a commit, or code
  review.
- The request is a focused engineering change with stable requirements.

## Where the product frame lives

| Question | Source |
| --- | --- |
| What is this product, and what will it never do? | ADR-0002 |
| Which markets, in what order? | ADR-0003 |
| When may a numeric threshold exist? | ADR-0004 |
| What do direction and magnitude each decide? | ADR-0005 |
| Why is execution off the table? | ADR-0018 |
| What future directions are proposed? | ADR-0019 to ADR-0022 (`proposed`) |
| What is undecided right now? | `docs/open-decisions.md` |
| What is built, and what is next? | `docs/implementation-status.md`, `docs/plan.md` |
| What must the behavior satisfy? | `docs/research-spec.md`, `docs/validation-gates.md` |

## Workflow

1. Read `docs/adr/README.md` first, then this checklist.
2. Inspect only the project docs needed to answer the specific question. Treat
   README, goals, specs, plans, status, and gates as **evidence**, not as a
   fresh source of product identity on every turn.
3. State the active product frame from the ADRs before recommending work. Do
   not restate or maintain a competing product-frame definition anywhere.
4. Run the checks below against the proposal before giving a plan.
5. If the logic is not closed, ask targeted questions before proposing a phase
   or PR sequence. If an assumption is safe, state it explicitly.
6. When proposing work, describe product value, decision-usefulness value, scope
   risk, minimum PR shape, and manual verification.
7. If a document conflicts with an ADR, name both and propose the fix. Do not
   resolve it silently in either direction, and do not treat document length or
   conservative wording as authority.

## Checks

1. **TW-first read as TW-only?** ADR-0003 makes market sequencing a phase, not a
   ceiling. Contracts stay market-agnostic.
2. **Is the proposed advance actually maintenance?** Hardening, docs cleanup,
   and comparison polish are real work but are not product advances unless they
   improve opinion quality.
3. **Execution creep?** Broker connectivity, live orders, order lifecycle, or
   platform-control surfaces contradict ADR-0018. Reversing it is a
   product-identity change requiring a new ADR, not a feature request.
4. **Opinion turning into advice?** ADR-0002 draws the line at model opinion
   with manual adoption. Personalized, situation-aware recommendations cross it.
5. **Invented thresholds?** Any new numeric cutoff — confidence, investability,
   drawdown, IC, turnover, or a blend weight between two signals — must satisfy
   ADR-0004.
6. **Forced output?** If evidence is insufficient, `no-opinion` and
   `do-not-adopt` are correct results. A proposal that cannot produce them is
   wrong.
7. **Is a limitation only recorded, not disclosed?** ADR-0005 requires the
   pooled-evidence gap to reach the user through invalidation notes. A
   limitation visible only in a document is a limitation hidden from the user.
8. **Does it improve decision usefulness for one solo investor-researcher?** If
   the answer needs a hypothetical second user, it is out of scope.

## Side-effect boundaries

- Prefer read-only inspection for strategy review.
- Do not edit files unless implementation was explicitly requested.
- Do not propose new dependencies, DB migrations, broker execution, live-order
  semantics, or platform-control surfaces unless the product direction is being
  deliberately changed.
- Do not invent stable numeric thresholds (see ADR-0004).
- Do not turn model opinions into personalized investment advice (see ADR-0002).

## Output shape

For a product-strategy request, return:

- `understanding` — the current product frame and the stated goal.
- `challenge` — contradictions, missing decisions, and drift findings.
- `recommendation` — the recommended direction and why alternatives are weaker.
- `phase_or_pr_plan` — a phase proposal or minimum PR slices, once the logic is
  closed.
- `manual_verification` — a checklist focused on product decision value.
