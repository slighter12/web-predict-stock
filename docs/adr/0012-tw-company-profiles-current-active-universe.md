---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-011
scope: TW daily
---

# The TW universe is a current-active selection filter, with no status history

Broad daily batch ingestion draws its universe from `tw_company_profiles`
filtered on `trading_status="active"`, filled and reconciled from official TWSE
and TPEX sources. Heavier per-symbol scheduling continues to use
`ingestion_watchlist`; the two are separate on purpose.

The important half of this decision is what it **does not** provide. The active
filter is a *selection* rule applied at ingestion time, not a retention rule and
not a historical record. Nothing deletes ingested daily rows — the only deletes
in `market_data` are for tick archives. This produces three distinct situations
that are easy to confuse:

1. **Symbols that delisted before backfill ran** were never in the
   current-active universe, so their price history does not exist locally and
   cannot be recovered from the current provider path. This price-coverage gap
   is fixed at backfill time and does not shrink.
2. **Symbols that delist while the system is running** drop out of the active
   filter, so ingestion stops — but every row already collected stays. The
   database does accumulate delisted-symbol history for the window since
   ingestion began.
3. **The profile table records current status only.** There is no `valid_from` /
   `valid_to` and no status event log, so the question "which symbols were
   active on a given past date" is unanswerable even for symbols whose price
   history we hold in full.

Situations 1 and 3 are separate limitations: historical price coverage cannot
answer historical membership, and adding membership history cannot create
price rows that the system never ingested.

## Consequences

- Survivorship bias applies to the **pre-ingestion window** and **decays over
  time** for the forward window. It is not a fixed property of the dataset, and
  describing it as one would be wrong in both directions — too pessimistic about
  recent data, too optimistic about deep history.
- Backtests reaching into the pre-ingestion window may be optimistic by an
  unquantified margin. This must be stated where results are read, not only
  here.
- A successful new TW run persists this warning. Reload projection also exposes
  a non-blocking comparison caveat with code
  `TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE`; legacy TW runs derive the same
  note from their saved market or request payload. The caveat remains visible
  without changing comparison eligibility or opinion viability by itself.
- **The blocker for answering point-in-time membership is status history.**
  Adding validity ranges or a status event log to `tw_company_profiles` would
  make situation 2 answerable; it would not repair situation 1's historical
  price-coverage gap.
- Scoped to TW daily. A US lane needs its own universe decision (ADR-0021),
  where point-in-time listing data may be more readily available.
