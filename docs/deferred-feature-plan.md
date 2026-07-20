# Deferred Feature Plan

This document records feature families that are intentionally outside the v1
research workbench. It is a planning placeholder, not an implementation spec or
developer operations guide.

## Purpose

- prevent removed advanced documentation from being mistaken for v1 scope
- keep future feature candidates visible without making them default workflow
  requirements
- define the minimum bar before a deferred feature can re-enter active planning

## Historical Context

The repository originally carried broader platform and operations ambitions.
During the v1 workbench refocus, parts of that surface were removed from the
main user journey or rewritten as secondary diagnostics because they made the
product direction hard to read.

Some code and metadata from that period remains intentionally:

- to preserve compatibility with existing persisted records and migrations
- to keep internal diagnostics available while TW daily research data is made
  reliable
- to avoid deleting foundations that may become future work after a promotion
  decision

Those retained foundations are not current v1 commitments. They should not be
used to justify adding execution, adaptive, peer, factor, external-signal, tick
archive, or broad data-control workflows back into Start, Builder, or
Experiments.

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
| Broker or live-order execution | deferred | What guarded execution safety model, reconciliation, audit, kill-switch, and manual-confirmation rules are required before this becomes active? |
| Simulation-platform integration | deferred | Which simulator is the baseline, and what comparison artifact does it produce? |
| Adaptive or RL workflow | deferred | What researcher decision does adaptation explain better than static experiments? |
| Peer inference and clustering | deferred | Which v1 analysis question needs peer context, and how is leakage avoided? |
| Broad factor catalog expansion | deferred | Which factors are required for the baseline TW daily task family? |
| External-signal breadth | deferred | Which signal timing and audit rules make it research-safe? |
| Tick archive and intraday strategy UX | deferred | Is intraday analysis part of a future product, or only a data-foundation tool? |
| Data-control completeness | deferred | Which controls are needed for the workbench user, not platform admins? |
| Portfolio auto-control | deferred | What manual adoption and portfolio-impact evidence must exist before automatic controls are considered? |
| US daily parity | deferred | Which market-calendar, raw-source audit, and provider-contract rules are required before US daily becomes active scope? |

## External Reference Inventory

External projects can inform local method design, data contracts, and future
phase planning. They are not default dependencies, runtime platforms, or proof
that a deferred capability belongs in the current workflow.

| Reference | Keep for later | Do not import now |
| --- | --- | --- |
| `Jesse` | strategy lifecycle, signal-to-position translation, robustness checks, parameter sensitivity, backtest-report discipline, paper/live separation, order lifecycle concepts | trading framework runtime, exchange adapters, live trading loop, crypto assumptions |
| `UZI-Skill` | multi-angle report structure, self-review gates, evidence/risk/invalidation sections, compact stock-analysis brief patterns | skill runtime, report generator dependency, personalized advice claims |
| `a-stock-data` | data-source catalog, raw-payload traceability, parser versions, source fallback patterns, zero-key source caveats | A-share-specific endpoint layer, unofficial scraping assumptions, broad data platform scope |
| `OpenBB` | provider abstraction, source-agnostic data access, future US daily source planning | full SDK or terminal integration before source contracts are chosen |
| `FinGPT` | text evidence extraction, research-report summarization, risk/warning/invalidation support | LLM-generated trade decisions or unverified investment advice |
| `FinRL` | train/test/trade separation, environment separation, benchmark and policy evaluation concepts | RL/adaptive control workflow before static research opinions are useful |
| `Hummingbot` and `Freqtrade` | far-future execution safety references only if guarded execution becomes active | crypto trading bot behavior, market-making runtime, live execution as a product shortcut |

## Promotion Criteria

These criteria define when a reference or deferred capability can move from
planning inventory into active implementation. Meeting these criteria does not
automatically promote the feature; it makes the feature eligible for an update
to `docs/plan.md` and `docs/validation-gates.md`.

| Candidate | Can enter active planning when | Must stay deferred when |
| --- | --- | --- |
| Research method library | the first method uses existing persisted research artifacts, defines its output artifact, includes a validation check, and preserves comparison caveats | the method requires a new external runtime, new data platform, or live execution loop |
| Jesse-style methods | the idea is implemented locally as strategy lifecycle, signal-to-position translation, robustness check, parameter sensitivity, or report discipline | the proposal imports Jesse runtime, exchange adapters, crypto assumptions, or live trading behavior |
| UZI-Skill-style reporting | the report pattern maps to opinion rows with evidence, risk, invalidation, and self-review checks | the proposal depends on the skill runtime, generated advice copy, or untraceable report conclusions |
| a-stock-data-style intake | the source can be represented through raw payload preservation, parser version, fetch status, and source fallback metadata | the source relies on unreviewed scraping, market-specific shortcuts, or broad data-control UX |
| OpenBB-style provider abstraction | the provider contract is market-aware, source-audited, and useful for TW daily or a documented US daily expansion | the proposal adds a full terminal or SDK integration before source contracts are chosen |
| FinGPT-style evidence extraction | text evidence is traceable to source material and supports evidence reason, risk, warning, or invalidation fields | LLM output produces unverified trade decisions or personalized advice |
| FinRL or adaptive methods | a static opinion baseline exists and the policy-evaluation artifact, benchmark, and rollback criteria are specified | adaptive behavior would alter live decisions, strategy controls, or portfolio actions without a research-only evaluation contract |
| Broker or live-order execution | safety model, idempotency, reconciliation, audit logs, manual confirmation, and kill switch gates are documented and accepted | the feature is proposed as a shortcut from opinion output to orders |
| Portfolio auto-control | manual adoption tracking and portfolio-impact measurement already exist and define the evidence needed for automatic controls | the feature would rebalance, size positions, or control accounts before manual-adoption evidence exists |
| US daily parity | market calendar, provider contract, raw-source audit, and TW/US comparison semantics are documented | the work is only a provider swap without data-readiness and comparability rules |

## Near-Term Interpretation

The next backend-oriented product slice should treat external references as
method inputs for a local research method library and opinion artifact contract.
It should not add new external runtimes, frontend surfaces, broker connectors,
or account-control behavior.

## Current Todo

- keep deferred modules out of the v1 main workflow
- avoid adding developer-runbook details for deferred modules to `docs/dev.md`
- replace removed runbook content with feature-plan decisions only when a
  product question is ready to answer
- update `docs/decision-register.md` before promoting any deferred candidate
