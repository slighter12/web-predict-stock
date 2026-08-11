---
status: proposed
date: 2026-08-10
---

# Fundamental Research Track complements the Technical Research Track

**Proposed.** This records an intended direction and the conditions that must be
met before it can be accepted. It is not a commitment to build.

The intent is to add a Fundamental Research Track driven by valuation ratios,
earnings quality, and balance-sheet metrics alongside the existing Technical
Research Track.

The Fundamental Research Track and Technical Research Track are separate
research tracks, not Prediction Tasks. Each track may contain
regression or classification Prediction Tasks, selected for the question,
target, horizon, and diagnostics being studied.

Fundamental inputs keep their own publication-date and evaluation semantics.
They are not automatically appended to the Technical Research Track's daily
Feature matrix: quarterly figures are near-constant within a quarter and jump
on announcement, so placing them in a daily model can create a discontinuity
artifact rather than a valuation signal.

Whether the two tracks ever contribute to one Opinion Artifact is deliberately
out of scope here. Any combination would require a blend weight, which under
ADR-0004 needs its own justification and decision.

## Conditions before acceptance

1. **Announcement-date alignment.** Fundamentals must be joined by the date the
   figure was *published*, never by the fiscal period it covers. Period-end
   alignment is the classic lookahead bug in fundamental backtesting and it
   would invalidate results silently.
2. **Restatement handling.** A decision is needed on whether restated figures
   replace or version the original. Overwriting means historical runs can no
   longer be reproduced, which conflicts with ADR-0015.
3. **Universe honesty.** ADR-0012's pre-ingestion survivorship gap hurts value
   research more than momentum research, because names missing from deep
   history are disproportionately the ones that looked cheap before failing. A
   point-in-time universe may be a hard prerequisite here rather than an
   accepted caveat.
4. **Horizon and evaluation semantics** defined: target, holding period,
   rebalance frequency, and how a multi-quarter backtest is validated against
   the limited history available.
5. **Scope collision resolved.** `docs/project-goals.md` defers factor catalog
   expansion beyond baseline inputs, and ADR-0017 keeps the factor catalog as
   an internal foundation. Accepting this ADR promotes that module and requires
   updating both.
