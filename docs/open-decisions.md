# Open Decisions

Policy gaps where **no decision has been made and no direction is settled**.
Decisions that were made live in [`adr/`](adr/); a known direction awaiting
evidence is a `proposed` ADR, not an entry here. See ADR-0001.

| ID | Legacy ID | Topic | Owner area | What it blocks | Acceptance trigger |
| --- | --- | --- | --- | --- | --- |
| `OPEN-001` | — | Per-symbol direction diagnostics | model governance | An honest per-symbol admission claim in ADR-0005 | Per-symbol holdout and calibration diagnostics exist, with a stated minimum-support rule, so the admission gate can claim symbol-level rather than pooled evidence |
| `OPEN-002` | `TBD-V1-002` | Persisted artifact retention and size bounds | research persistence | Long-running research-run history under ADR-0007 and ADR-0015 | It is decided whether diagnostic samples, signals, and equity curves are stored in full or bounded per run, and what happens to runs that exceed the bound |
| `OPEN-003` | `TBD-V1-003` | Comparison reason hardening | research-run comparison UX | Richer pairwise comparison explanations | Backend caveats extend beyond artifact completeness and stay aligned with UI-derived assumption-mismatch labels |
| `OPEN-004` | `TBD-001` | TW calibrated minimum traded-value floor | research policy | Any investability claim | A calibration methodology, acceptance rule, and versioned floor are published under ADR-0004 |
| `OPEN-005` | `TBD-002` | Tick archive storage details | data platform | Durable tick archive qualification; the single-store assumption in ADR-0007 | Archive naming, compression, partitioning, retention, and restore qualification are frozen |
| `OPEN-006` | `TBD-003` | Simulation platform choice | execution research | Simulation readback and failure-taxonomy measurement | A platform is selected, without crossing ADR-0018 |
| `OPEN-008` | `TBD-005`, `TBD-PHASE-004` | Guarded broker execution safety model | execution planning | Any reversal of ADR-0018 | Safety model, audit, reconciliation, idempotent submission, manual confirmation, and kill-switch gates are all documented **before** broker work may enter planning |
| `OPEN-009` | `TBD-006` | Portfolio auto-control boundary | portfolio research | Any automation beyond ADR-0022 | Manual adoption tracking and portfolio-impact measurement exist and have been evaluated first |
| `OPEN-010` | — | Point-in-time universe status history | data platform | Any absolute historical performance claim; the Fundamental Research Track in ADR-0020 | `tw_company_profiles` carries validity ranges or a status event log, so past-date active membership is answerable for the post-ingestion window; ADR-0012 separately tracks unavailable historical price coverage |
| `OPEN-011` | — | Reconciliation coverage-ratio threshold | data platform | ADR-0004 compliance for the guard in ADR-0023 | The literal coverage ratio guarding internal company-profile reconciliation is either labelled provisional or replaced by a named, versioned policy with a written rationale |

## Rules

- An entry leaves this file in one of two ways: it becomes an ADR, or it is
  explicitly dropped as no longer relevant. It does not quietly disappear.
- `OPEN-008` and `OPEN-009` are listed as gates, not as roadmap items. Their
  presence here is not evidence that the work is planned.
- IDs are stable and never reused. `Legacy ID` records the entry's identifier
  in the retired `docs/decision-register.md`; `—` means the gap was first
  identified after that file was retired.
