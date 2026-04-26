# Deferred Feature Plan

This document records feature families that are intentionally outside the v1
research workbench. It is a planning placeholder, not an implementation spec or
developer operations guide.

## Purpose

- prevent removed advanced documentation from being mistaken for v1 scope
- keep future feature candidates visible without making them default workflow
  requirements
- define the minimum bar before a deferred feature can re-enter active planning

## Promotion Rule

A deferred feature can move into `docs/plan.md` only after it has:

- a target user workflow
- a clear relationship to regression or classification analysis
- required data contracts and persistence rules
- acceptance checks in `docs/validation-gates.md`
- an information-architecture decision for where the feature appears
- a migration or compatibility plan if existing records are affected

Until then, deferred features should not appear in the default Start, Builder,
or Experiments workflow.

## Deferred Candidates

| Candidate | Current decision | Re-entry question |
| --- | --- | --- |
| Broker or live-order execution | deferred | Does this help research analysis, or is it a separate trading product? |
| Simulation-platform integration | deferred | Which simulator is the baseline, and what comparison artifact does it produce? |
| Adaptive or RL workflow | deferred | What researcher decision does adaptation explain better than static experiments? |
| Peer inference and clustering | deferred | Which v1 analysis question needs peer context, and how is leakage avoided? |
| Broad factor catalog expansion | deferred | Which factors are required for the baseline TW daily task family? |
| External-signal breadth | deferred | Which signal timing and audit rules make it research-safe? |
| Tick archive and intraday strategy UX | deferred | Is intraday analysis part of a future product, or only a data-foundation tool? |
| Operations-console completeness | deferred | Which operational controls are needed for the workbench user, not platform admins? |

## Current Todo

- keep deferred modules out of the v1 main workflow
- avoid adding developer-runbook details for deferred modules to `docs/dev.md`
- replace removed runbook content with feature-plan decisions only when a
  product question is ready to answer
- update `docs/decision-register.md` before promoting any deferred candidate
