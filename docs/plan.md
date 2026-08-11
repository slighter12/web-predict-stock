# Implementation Roadmap

## Purpose

Define delivery sequencing, dependency rules, and completion logic for the
`TW daily Quant ML Research Workbench` v1.

## Owns

- v1 milestone order
- phase sequencing beyond v1
- dependency policy
- completion criteria
- hidden-advanced boundaries

## Does Not Own

- local developer workflow
- exact KPI formulas or thresholds
- open decision definitions
- long-term execution or adaptive platform delivery

## Consumes

- `docs/project-goals.md` for strategic priority
- `docs/research-spec.md` for normative behavior and persisted artifact rules
- `docs/validation-gates.md` for v1 acceptance checks and deferred-gate labels

## Produces

- v1 milestone IDs
- delivery order and dependency policy
- explicit advanced/deferred module boundaries

## Decision Rule

Use this document when deciding what should be built next and which work is
allowed to appear in the main research workflow.

## Planning Model

V1 uses three completion states:

- `contract-defined`
  the behavior and artifact shape are documented
- `implemented`
  the backend and frontend support the behavior
- `persisted-reviewable`
  a historical run can be reloaded with the same result quality as the
  in-session run

No v1 milestone depends on execution, live trading, adaptive workflows, peer
inference, broad factor expansion, or tick archive operations.

## V1 Milestones

| Milestone | Primary goals | Primary outcome | Completion state target |
| --- | --- | --- | --- |
| `V1-Docs` | `G1` to `G6` | README, goals, plan, spec, and gates all describe a research workbench before a platform | `contract-defined` |
| `V1-IA` | `G2`, `G3` | main UI starts with a baseline research run, recent research runs, and data readiness | `implemented` |
| `V1-Diagnostics` | `G3`, `G4` | regression run response and persisted record include model diagnostics | `persisted-reviewable` |
| `V1-Artifacts` | `G2`, `G5` | persisted run stores every artifact required by `SPEC-RUN-001` | `persisted-reviewable` |
| `V1-Run-Comparison` | `G6` | research runs can be searched, filtered, sorted, loaded, and compared with caveats | `implemented` |
| `V1-Classification-Spec` | `G3` | classification task fields and diagnostics are specified but not required in first code delivery | `contract-defined as part of V1-Docs` |

`V1-Run-Comparison` was formerly named `V1-Experiments`; it was renamed when
`CONTEXT.md` made `Research run` the canonical term.

## Delivery Order

1. `V1-Docs`
2. `V1-Classification-Spec`
3. `V1-IA`
4. `V1-Diagnostics`
5. `V1-Artifacts`
6. `V1-Run-Comparison`

`V1-Classification-Spec` is listed separately for visibility, but it is part of
the documentation contract and should be completed with `V1-Docs`, not after
the implementation milestones.

`V1-Diagnostics` and `V1-Artifacts` should be implemented together when the
database contract changes, because model diagnostics are not useful if they only
exist in the latest in-session response.

## Phase 2 Sequencing

Migrated from the retired `docs/decision-register.md`: this section carries
`DEC-PHASE-003`, and retires `DEC-PHASE-009` below.

Phase 2 is **backend-first**. Diagnostics, signals, backtests, baselines, and
warnings are synthesized into decision-useful opinion artifacts before any large
new UI surface is added. Opinion quality is the product advance; a UI that
presents a weak opinion more attractively is not.

Normative behavior for the opinion layer lives in `SPEC-OPINION-*`
(`docs/research-spec.md`) and `GATE-P2-*` (`docs/validation-gates.md`).
The boundary on what an opinion may claim is ADR-0002; the shape of the
prediction it rests on is ADR-0005.

### Retired: retain-the-current-UI (`DEC-PHASE-009`)

`DEC-PHASE-009` held that the existing hybrid review UI should stay in place
untouched while Phase 2 remained backend-first. **That decision is retired.**
Preserving the existing UI is no longer product intent: the frontend rewrite is
planned but has not started. No active frontend feature development is underway;
the backend-first pause remains in effect while backend contracts and evaluation
mature. Backend-first sequencing above still holds; it is the ordering that
survives, not the freeze.

The planned frontend rewrite will align the canonical `Research run` term with
the existing frontend surface labels; `docs/` already uses the canonical term.

## Dependency Rules

### Must Exist Before Later Work

- `V1-Docs` before UI or API changes that could widen scope
- `V1-IA` before adding advanced surfaces to the homepage
- `V1-Diagnostics` before treating strategy metrics as the result-page center
- `V1-Artifacts` before claiming persisted research runs are reviewable
- `V1-Run-Comparison` before adding richer comparison scoring

### Hidden Advanced Policy

Execution, adaptive, peer, factor, external-signal, and tick archive work may
remain reachable through secondary diagnostics or backend APIs, but these
capabilities must not be required to start or understand a baseline research
run.

### Deferred Work

The following are future candidates with no v1 delivery commitment:

- guarded broker execution
- simulation-platform readback qualification
- RL or adaptive model control
- peer inference and clustering as default context
- broad factor catalog and external-signal expansion
- intraday or tick-based strategy claims
- US-market parity

## Practical Reading Order

When planning a change:

1. confirm the work belongs under `docs/project-goals.md`
2. confirm required behavior in `docs/research-spec.md`
3. locate the milestone in this file
4. confirm the acceptance check in `docs/validation-gates.md`
5. check `docs/implementation-status.md` when existing advanced code may be
   confused with v1 product scope
