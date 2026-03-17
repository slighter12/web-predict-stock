# Implementation Roadmap V2

## Purpose

Define delivery sequencing, dependency rules, and phase-level completion logic.

## Owns

- phase order and dependency rules
- phase exit-gate mapping
- operational validation ordering
- allowed parallelization boundaries

## Does Not Own

- runtime or execution semantics
- KPI formulas, thresholds, or gate truth conditions
- local developer workflow
- open decision definitions

## Consumes

- `docs/project-goals.md` for strategic priority
- `docs/research-spec.md` for normative behavior and metadata requirements
- `docs/validation-gates.md` for gate IDs and pass conditions
- `docs/decision-register.md` for open `TBD-*` decision status

## Produces

- phase IDs `P0` to `P11`
- delivery order and dependency policy
- phase-to-gate mapping used for planning and review

## Decision Rule

Use this document when deciding what should be built next, which phases can run
in parallel, and which phase gates should unblock downstream work.

## Planning Model

The roadmap uses three completion states and two gate layers:

- `structural-complete`
  required artifacts and metadata exist
- `sample-complete`
  the phase has enough reproducible sample history to evaluate its linked KPIs
- `performance-qualified`
  optional claim state for policy, adoption, or performance assertions after
  structural and sample completion
- phase exit gate
  engineering-completion gate that unblocks dependent work
- operational validation gate
  observation-window gate that unlocks mature monitoring or governance claims

## Planning Rules

- Each phase should reach a usable baseline before dependent phases begin.
- A phase may be `structural-complete` before its long-window KPI history
  exists.
- Dependent engineering work should be gated by the phase exit gate, not by
  the operational validation gate, unless the downstream phase explicitly
  depends on a mature observation window.
- No phase should depend on metadata introduced only by a later phase in order
  to become `structural-complete`.
- `performance-qualified` should remain optional unless a policy or performance
  claim is being made.

## Phase Summary

| Phase | Primary goals | Primary outcome | Exit gate | Operational gate |
| --- | --- | --- | --- | --- |
| `P0` | `G2`, `G3`, `G9` | runtime and comparison alignment | `GATE-P0-001` | none |
| `P1` | `G1`, `G2` | TW daily ingestion and recovery | `GATE-P1-001` | `GATE-P1-OPS-001` |
| `P2` | `G1`, `G2`, `G8` | tick archive preservation | `GATE-P2-001` | `GATE-P2-OPS-001` |
| `P3` | `G1`, `G3`, `G9` | tradability-state and execution-universe gating | `GATE-P3-001` | `GATE-P3-OPS-001` |
| `P4` | `G2`, `G3`, `G5` | run registry and comparison governance | `GATE-P4-001` | `GATE-P4-OPS-001` |
| `P5` | `G3`, `G9` | daily strategy and backtest alignment | `GATE-P5-001` | `GATE-P5-OPS-001` |
| `P6` | `G4` | model-family expansion on a shared contract | `GATE-P6-001` | `GATE-P6-OPS-001` |
| `P7` | `G5`, `G6` | external signals and factor expansion | `GATE-P7-001` | `GATE-P7-OPS-001` |
| `P8` | `G7` | clustering and peer inference | `GATE-P8-001` | `GATE-P8-OPS-001` |
| `P9` | `G9` | simulation platform integration | `GATE-P9-001` | `GATE-P9-OPS-001` |
| `P10` | `G9` | guarded broker execution | `GATE-P10-001` | `GATE-LIVEQ-001` |
| `P11` | `G10` | RL and adaptive extensions | `GATE-P11-001` | none |

## Delivery Order

The intended order is:

1. `P0`
2. `P1`
3. `P2`
4. `P3`
5. `P4`
6. `P5`
7. selected work in `P6`, `P7`, and `P8`
8. `P9`, `P10`, and `P11`

## Dependency Rules

### Must Exist Before Later Phases

- `P0` before any phase that depends on runtime-mode or default-bundle clarity
- `P1` before any claim that depends on durable raw-data recovery
- `P3` before any investability or execution-readiness workflow
- `P4` before governance-heavy comparison workflows
- `P5` before benchmark-relative strategy claims

### Safe Parallelization

After `P3`, selected work in `P6`, `P7`, and `P8` may run in parallel when all
participants use the same active spec contract and the same gate vocabulary.

### Must Remain Downstream

- `P9` should not start as a primary workstream before the baseline research
  stack is stable
- `P10` should remain downstream of simulation-path controls
- `P11` should remain downstream of the accepted non-adaptive baseline

## Phase Details

| Phase | Goal | Depends on | Exit gate | Operational gate | Decision dependency |
| --- | --- | --- | --- | --- | --- |
| `P0` | align runtime modes, default-bundle behavior, and comparison labels | none | `GATE-P0-001` | none | none |
| `P1` | build durable TW-first daily ingestion with replay and recovery | `P0` | `GATE-P1-001` | `GATE-P1-OPS-001` | none |
| `P2` | preserve raw tick archives before formal intraday claims | `P1` | `GATE-P2-001` | `GATE-P2-OPS-001` | `TBD-002` for durable operational qualification |
| `P3` | add explicit tradability-state and execution-universe logic | `P1` | `GATE-P3-001` | `GATE-P3-OPS-001` | none |
| `P4` | make runs reproducible, comparable, and reviewable | `P0`, `P3` | `GATE-P4-001` | `GATE-P4-OPS-001` | none |
| `P5` | align labels, execution semantics, threshold policy, and benchmark reporting | `P3`, `P4` | `GATE-P5-001` | `GATE-P5-OPS-001` | `TBD-001` for durable policy qualification |
| `P6` | add ML and DL families without breaking the shared contract | `P4`, `P5` | `GATE-P6-001` | `GATE-P6-OPS-001` | `TBD-004` for cross-family default policy hardening |
| `P7` | add external signals and factor expansion without timing leakage | `P4`, `P5` | `GATE-P7-001` | `GATE-P7-OPS-001` | none |
| `P8` | add point-in-time clustering and peer inference | `P4`, `P5` | `GATE-P8-001` | `GATE-P8-OPS-001` | none |
| `P9` | connect the stack to a simulation environment with readback | `P5` | `GATE-P9-001` | `GATE-P9-OPS-001` | `TBD-003` for durable operational qualification |
| `P10` | move from simulation to guarded broker execution | `P9` | `GATE-P10-001` | `GATE-LIVEQ-001` | none |
| `P11` | isolate adaptive methods from the default baseline | `P5` | `GATE-P11-001` | none | none |

## Practical Reading Order

When planning a change:

1. confirm the work matters under `docs/project-goals.md`
2. confirm required behavior in `docs/research-spec.md`
3. locate the phase in this file
4. confirm the gate in `docs/validation-gates.md`
5. check `docs/decision-register.md` when a `TBD-*` dependency appears
