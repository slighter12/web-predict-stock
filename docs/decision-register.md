# Decision Register

This document is descriptive and governing only for open `TBD-*` decision
tracking. It is not a runtime-spec document.

## Purpose

- record open `TBD-*` decisions in one place
- assign an owner area, blocking impact, and next action to each decision
- prevent open-decision prose from being duplicated across spec, plan, and
  gates

## Owns

- the authoritative definitions of `TBD-001` to `TBD-004`
- decision status and owner area
- blocking impact and next-step tracking

## Does Not Own

- runtime or execution semantics
- KPI formulas, thresholds, or gate truth conditions
- phase ordering
- local developer workflow

## Consumes

- `docs/research-spec.md` for spec dependencies
- `docs/plan.md` for roadmap dependencies
- `docs/validation-gates.md` for gate dependencies

## Produces

- the single source of truth for all open `TBD-*` definitions
- a review surface for policy-blocking and telemetry-only decisions

## Decision Rule

When a document needs to reference an unresolved policy or platform decision,
it should cite the `TBD-*` ID and route readers here for the definition,
status, and next action.

## Decision Summary

| ID | Topic | Status | Owner area | Blocks | Next action |
| --- | --- | --- | --- | --- | --- |
| `TBD-001` | TW calibrated minimum traded-value floor | open | research policy | durable investability policy and benchmark-relative policy qualification | define calibration method and promote a non-zero floor when approved |
| `TBD-002` | tick archive storage details | open | data platform | durable `P2` operational qualification | freeze archive naming, compression, partitioning, and retention baseline |
| `TBD-003` | simulation platform choice | open | execution integration | durable `P9` operational qualification | select the baseline simulation platform and fix failure-taxonomy scope |
| `TBD-004` | cross-model missing-feature default policy | open | model governance | default cross-family policy hardening in `P6` | define the shared default policy beyond per-family declarations |

## Decision Details

### TBD-001

- Topic: TW calibrated minimum traded-value floor
- Status: open
- Owner area: research policy
- Definition:
  the v1 default remains `0`, but a TW-specific calibrated traded-value floor
  is still required before investability claims, investability-based threshold
  recalibration, or benchmark-relative policy qualification become durable
  policy.
- Blocking impact:
  `GATE-POLICY-001` and benchmark-relative policy interpretation remain
  exploratory until this decision is resolved.
- Next action:
  publish the calibration methodology, acceptance rule, and adopted floor
  version.

### TBD-002

- Topic: tick archive storage details
- Status: open
- Owner area: data platform
- Definition:
  archive naming, compression, partitioning, and retention details are not yet
  frozen as the binding storage baseline.
- Blocking impact:
  `KPI-TICK-*` telemetry may be trended, but `GATE-P2-OPS-001` should not be
  treated as durable until the storage baseline is fixed.
- Next action:
  freeze the archive policy and benchmark profile expectations used for restore
  and compression evaluation.

### TBD-003

- Topic: simulation platform choice
- Status: open
- Owner area: execution integration
- Definition:
  the execution roadmap still needs one simulation platform to be fixed as the
  baseline for readback, reconciliation, and failure-taxonomy measurement.
- Blocking impact:
  `KPI-SIM-*` telemetry may be trended, but `GATE-P9-OPS-001` should not be
  treated as durable until the platform baseline is fixed.
- Next action:
  select the platform and document the readback and failure-taxonomy boundary.

### TBD-004

- Topic: cross-model missing-feature default policy
- Status: open
- Owner area: model governance
- Definition:
  per-family missing-feature declarations exist, but a shared cross-family
  default policy is not yet frozen.
- Blocking impact:
  cross-family adoption review should keep relying on
  `missing_feature_policy_version` parity until a default policy is approved.
- Next action:
  define the shared default behavior or state explicitly that no shared default
  will exist.
