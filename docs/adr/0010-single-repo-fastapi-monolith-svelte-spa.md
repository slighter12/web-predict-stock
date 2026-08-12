---
status: accepted
date: 2026-08-10
---

# One repository, one FastAPI backend, one Svelte SPA

Backend (FastAPI, Python 3.12) and frontend (Svelte 5 SPA with TanStack Query
and ECharts, built by Vite) live in the same repository and are versioned
together. There is no service decomposition and no separate frontend repo.

For a single-researcher tool, the contract between backend and frontend changes
constantly as artifact shapes evolve. Keeping both in one repository makes a
contract change one commit instead of a coordinated release, and premature
microservice decomposition is an explicit non-goal.

Svelte over React was chosen for the compile-time model and the absence of a
runtime state-management layer; ECharts over a React-centric charting library
because the heavy surfaces here are dense financial time series, and TanStack
Query because server state — runs, artifacts, readiness — is nearly all the
state the UI has.

## Consequences

- Frontend types must be regenerated or hand-synced when backend contracts move;
  the architecture test does not cover this seam.
- The frontend is not independently deployable, which is acceptable while there
  is one user.
