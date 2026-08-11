---
status: proposed
date: 2026-08-10
---

# Sentiment Feature Family feeds existing Prediction Tasks

**Proposed.** This records an intended direction and the conditions that must be
met before it can be accepted. It is not a commitment to build.

The intent is to add a Sentiment Feature Family — news, institutional
buying/selling flow, and text-derived sentiment — to the existing research
loop.

`external_signal` is an ingestion/audit layer. It preserves provider
payloads, source metadata, parser versions, and public-availability timestamps;
it does not produce an independent Opinion source.

Derived sentiment features feed the existing Prediction Tasks. They may affect
the Direction Gate and Magnitude Ranking, but they do not create a separate
Opinion source or action list.

Sentiment features remain subject to ADR-0011: provider payloads are preserved
with source and parser metadata attached.

## Conditions before acceptance

1. **Point-in-time integrity.** Every sentiment observation must carry the
   timestamp at which it was *publicly available*, not the timestamp of the
   event it describes. Sentiment data is the easiest place in this system to
   leak future information, and a leak here would silently inflate every
   diagnostic downstream.
2. **Source contract and licensing.** Named sources with stable schemas and
   terms that permit storage. Scraped sources with no contract do not qualify.
3. **Any text-to-score model is bound by ADR-0004.** A sentiment score produced
   by an LLM or a lexicon is a numeric judgment with an implicit threshold; it
   must be versioned and explainable, or labeled provisional wherever it affects
   output.
4. **Incremental evidence.** The baseline loop's diagnostics must be trustworthy
   first, and derived features must show diagnostic improvement over the
   existing Feature set — otherwise this is feature breadth without evidence,
   which the project's priority order explicitly defers.
