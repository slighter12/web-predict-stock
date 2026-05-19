# Product Compass

## Product Identity

This project is a market-phased quant research-to-opinion workbench.

It should help a solo investor-researcher turn quantitative research artifacts
into model-backed opinions that are useful before manual investment decisions.
It is not only a research artifact viewer, and it is not a broker, live trading,
or personalized portfolio-advice system.

## Market Sequence

- First implementation lane: TW daily.
- Future expansion lane: US daily.
- Product identity: market-phased and market-expandable, not TW-only.
- Phase 2 work should keep contracts and concepts market-agnostic while proving
  the loop first on TW daily data.

## Strategic Gap

The v1 usable loop can create, inspect, reload, and compare research runs. The
remaining product gap is that diagnostics, signals, backtests, baselines, and
warnings are not yet synthesized into a decision-useful opinion layer.

Avoid mistaking v1 hardening, docs cleanup, or comparison polish for the main
Phase 2 product advance unless it directly improves opinion quality.

## Phase Direction

### Phase 2: Research Opinion Layer

Phase 2 should produce an action-list opinion brief from existing research
artifacts.

The brief should include:

- strategy-level viability or no-opinion state
- buy-candidate list
- sell/avoid list
- watch list
- evidence and risk context for each list item
- invalidation notes explaining when the opinion should not be adopted

Minimum row fields:

- symbol
- model score
- strategy-derived weight or position signal
- evidence reason
- risk or warning
- invalidation note

The system does not need to know the user's holdings in Phase 2. A sell/avoid
list is a model opinion about symbols, not a statement that the user owns those
symbols or an instruction to place orders.

### Phase 3 North Star

Tracked portfolio ledger is a later product north star. It can close the loop
around adoption, holdings, forward outcomes, and portfolio impact, but it should
not be required for the Phase 2 opinion brief unless the user explicitly
reprioritizes the roadmap.

## Opinion Boundary

The product may use direct action-language labels when useful, but the boundary
is:

- model opinion, not personalized investment advice
- manual adoption, not broker instruction
- next-session planning from daily data, not intraday execution judgment

When evidence is insufficient, the product must be allowed to output
`no-opinion` or `do-not-adopt` instead of forcing a buy list.

## Threshold Policy

During prototype validation, provisional thresholds are allowed only when they
are clearly labeled as provisional.

Stable thresholds must eventually become versioned, explainable policy. Do not
invent permanent RMSE, IC, drawdown, turnover, confidence, or investability
thresholds without user approval and evidence.

## Success Model

Primary product success:

- decision usefulness: the tool helps the solo investor-researcher form a
  clearer model opinion faster.

Feedback validation:

- forward outcome versus baseline after the opinion date.

This means the product should eventually evaluate whether opinions helped, but
Phase 2 can start with the opinion artifact before building the Phase 3 ledger.

## Docs Conflict Rule

Existing docs are evidence and constraints. They are not allowed to erase this
product direction through length or conservative v1 wording.

If long docs imply that the project should remain research-only forever, flag
that as docs drift. If a proposal ignores current v1 boundaries and jumps to
broker/live execution, flag that as execution creep.

## Anti-Drift Checks

Before recommending roadmap, phase, or scope work, check:

- Is TW-first being misread as TW-only?
- Is Phase 2 being reduced to maintenance, hardening, or docs cleanup?
- Is the proposal jumping to broker execution, live orders, or platform-control
  surfaces too early?
- Is model opinion being turned into personalized investment advice?
- Are thresholds or confidence scores being invented without a provisional
  label or versioned policy?
- Is the system forcing buy/sell output when evidence should produce
  no-opinion?
- Does the proposal improve decision usefulness for a solo investor-researcher?
