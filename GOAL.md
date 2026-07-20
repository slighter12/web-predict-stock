# Goal Brief: Phase 2 Backend Opinion Expansion

## Context

### Background

This project is a market-phased quant research-to-opinion workbench. It helps a
solo investor-researcher turn persisted quantitative research artifacts into
model-backed opinions before manual investment decisions.

V1 can create, persist, reload, and compare TW daily research runs. Phase 2 must
turn those artifacts into a decision-useful backend opinion artifact. This is
an expansion of the backend opinion layer, not a replacement of existing
research-run artifacts and not a broker, live-order, or portfolio-control
feature.

External projects are reference material only:

- `Jesse`: strategy lifecycle, signal-to-position translation, robustness
  checks, parameter sensitivity, and backtest-report discipline.
- `UZI-Skill`: multi-angle report structure, self-review gates,
  evidence/risk/invalidation sections, and compact stock-analysis brief
  patterns.
- `a-stock-data` and `OpenBB`: source/provider audit concepts, raw-source
  traceability, parser/source metadata, and future market-aware provider
  contracts.
- `FinGPT`: traceable evidence extraction, report summarization, risk, warning,
  and invalidation support.
- `FinRL`: train/test/trade separation and policy evaluation for a later
  adaptive phase.

They must not become runtime dependencies, trading frameworks, broker adapters,
provider SDKs, or proof that deferred features belong in this goal.

### Implementation Baseline

Phase 2 backend work extends persisted research-run artifacts with an
`opinion_artifact` and structured `review_checks` results. Completion is
governed by the acceptance criteria and verification evidence below.

Required behavior before this goal can be complete:

- adding `review_checks` names and statuses alone is not enough
- latest signal selection must be by each symbol's latest persisted `date`;
  list order or last-write-wins replacement is not acceptable
- `parameter_sensitivity` always returning `not_evaluated` is not enough when
  persisted signals and effective strategy inputs exist
- `robustness` passing only because a `validation` object exists is not enough
- `source_artifact_audit` must not imply raw/provider/parser audit coverage
  when only config or fallback metadata exists
- `source_artifact_audit` must name missing `config_sources` and
  `fallback_audit` inputs when neither is present
- row evidence, risk, and invalidation must be row-specific for viable rows;
  shared generic payload references and static boilerplate are not enough
- UZI self-review gates must evaluate the actual row fields and references;
  a check must not pass merely because at least one row exists
- `manual_adoption_boundary` must inspect review-check copy as well as
  `state_reason` and row text, and must catch execution/advice wording variants
- list/read-summary paths must not expose action rows or prose derived from
  hidden heavy artifacts when those artifacts are omitted from the response
- tests that only check field presence, check names, or status values are not
  sufficient

Normative acceptance comes from:

- `docs/research-spec.md`
- `docs/validation-gates.md`
- `docs/decision-register.md`
- `docs/deferred-feature-plan.md`

`docs/implementation-status.md` is descriptive context only.

### Claim Boundary

Accepted Scope:

- preserve the existing backend `opinion_artifact` action-list slice
- extend `opinion_artifact.review_checks` with concrete local method results
- implement response/reload-time derived opinion checks from existing persisted
  research-run artifacts
- add focused backend tests that would fail against the current shallow
  implementation
- keep the work backend-first and research-only

Non-Claims:

- no frontend workflow
- no broker routing or live orders
- no personalized investment advice
- no automatic rebalancing or account-level portfolio control
- no US daily provider implementation
- no market-agnostic provider abstraction
- no TW/US comparison semantics
- no adaptive/RL control workflow
- no crypto trading behavior
- no Jesse, UZI-Skill, a-stock-data, OpenBB, FinGPT, FinRL, Hummingbot, or
  Freqtrade runtime dependency
- no DB migration unless deterministic reconstruction from existing persisted
  artifacts is proven impossible and the tradeoff is explicitly reported

Rejected Evidence:

- latest in-session response only
- metadata-only or partial records as proof of a valid opinion
- generic LLM confidence
- untraceable report prose
- imported external project behavior
- broad manual judgment without named evidence
- tests that only verify action-list shape, `review_checks` names, or statuses
- a `pass` status with an empty or unstable `result`
- config/fallback metadata treated as raw/provider/parser audit coverage
- list/summary action rows derived from hidden full `signals`

### Validation Lineage

- Current stage: Phase 2 backend opinion expansion over persisted V1
  research-run artifacts and the structured opinion contract.
- Direct dependency predecessor: persisted successful V1 research-run artifacts
  and the existing research-run create/reload/list API paths.
- Relevant prior final labels: V1 usable loop is described as verified in
  `docs/implementation-status.md`; Phase 2 opinion expansion is not complete.
- Required input artifacts: request payload, effective strategy,
  config/fallback metadata, version/policy metadata, metrics, model
  diagnostics, signals, validation, baselines, warnings, artifact completeness,
  missing artifacts, and comparison caveats already persisted or present on
  research-run responses.
- Regeneration/reproduction path: use focused backend tests under
  `tests/research/`; no external provider, broker, frontend, or runtime setup is
  required.
- Retry/turn ceiling: continue narrow fixes until acceptance evidence passes;
  report blocked only when the same blocker repeats for three consecutive
  attempts, focused tests cannot run after one environment/tooling retry, or
  completion requires forbidden scope.
- Runtime gate evidence: exact test commands, exit codes, reached/skipped
  attempt ledger, and focused output excerpts must be surfaced in the
  conversation.
- Result evidence sources: code diff, focused test output, `git diff --check`,
  and manual source review against the normative docs.

### Relevant Sources

- `docs/project-goals.md`
- `docs/plan.md`
- `docs/research-spec.md`
- `docs/validation-gates.md`
- `docs/decision-register.md`
- `docs/deferred-feature-plan.md`
- `docs/implementation-status.md`
- `backend/research/contracts/runs.py`
- `backend/research/domain/opinion.py`
- `backend/research/services/runs.py`
- `backend/research/repositories/runs.py`
- `tests/research/test_runs.py`
- `tests/research/test_research_api.py`
- `tests/research/test_run_repository.py`

### Constraints

- Repository artifacts stay in English.
- Keep edits minimal and backend-scoped.
- Prefer extending existing `opinion_artifact` over adding new top-level API
  fields.
- Prefer deterministic reconstruction from persisted run artifacts over adding
  persistence.
- Do not add new dependencies.
- Do not add a DB migration unless deterministic reconstruction is impossible
  and the reason is reported.
- Do not weaken existing research-run reload, comparison caveat, or hidden
  advanced-module boundaries.
- Do not infer unavailable data, provider metadata, source text, holdings, or
  live execution state.

### Non-Goals

- Frontend UI for opinions.
- Broker integration or live-order execution.
- Paper/live execution loop.
- Portfolio auto-control or automatic rebalancing.
- Manual adoption ledger or holdings-aware portfolio feedback loop.
- US daily provider implementation.
- Market provider abstraction or TW/US comparison policy.
- RL/adaptive control workflow.
- Personalized investment advice.
- Importing or wrapping Jesse, UZI-Skill, a-stock-data, OpenBB, FinGPT, FinRL,
  Hummingbot, or Freqtrade runtimes.

### Open Questions

- None block this goal. If a reference concept cannot be computed from existing
  persisted artifacts, expose the limitation in the artifact and completion
  evidence instead of widening scope.

## Goal

### Objective

Complete the Phase 2 backend opinion expansion so a persisted research run can
return a reloadable `opinion_artifact` that preserves action lists and adds
decision-useful local method results, self-review gates, source/provider audit
summaries, and traceable evidence summaries derived from existing artifacts.

The goal is not complete if the implementation merely labels reference concepts
as represented. Computable reference concepts must produce concrete results
that affect the opinion state, limitations, row evidence, or review-check
output.

### Deliverables

- Updated backend opinion contract where `OpinionReviewCheck` includes a
  stable `result` object.
- Deterministic opinion artifact builder that derives full detail/reload
  opinions from persisted research-run artifacts.
- Safe list/summary behavior that does not expose action rows or prose derived
  from omitted heavy artifacts.
- Focused tests covering contract, domain/service, repository reload/list, and
  API response paths.
- Completion report with test evidence, diff evidence, manual source audit, and
  no-scope-creep statement.

### Metric Type

`evidence_review`.

Completion requires named artifacts and checks: focused backend tests,
`git diff --check`, and manual review against `SPEC-OPINION-*`,
`GATE-P2-*`, accepted/deferred decisions, and this Goal Brief. Generic model
confidence, broad manual judgment, conversation memory, and field-presence-only
tests are insufficient.

### Evaluator Contract

Completion can be claimed only when the final response surfaces all of this
evidence:

- files changed
- selected schema and reload path
- exact focused test commands and exit codes
- the new or revised test that would fail against the current shallow
  implementation, with the behavior it protects
- `git diff --check` result
- acceptance status for every AC below
- manual audit against `docs/research-spec.md`, `docs/validation-gates.md`,
  `docs/decision-register.md`, and `docs/deferred-feature-plan.md`
- explicit statement that no frontend, broker/live execution, portfolio
  auto-control, US provider implementation, provider abstraction, adaptive/RL
  workflow, crypto trading behavior, or external runtime dependency was added

The evaluator must not assume hidden tool output, provider memory, unsurfaced
local state, or latest in-session response content.

### Contract Shape

Preserve the existing top-level `opinion_artifact` fields:

- `artifact_version`
- `state`
- `state_reason`
- `manual_adoption_only`
- `evidence_limitations`
- `buy_candidates`
- `sell_or_avoid`
- `watch`
- `review_checks`

Preserve populated action-list row fields:

- `symbol`
- `model_score`
- `position_signal`
- `evidence_reason`
- `risk_or_warning`
- `invalidation_note`
- `source_artifact_references`

Extend each `review_checks` item with one API contract field:

- `result`: an object containing the concrete local result for that check

Keep existing `review_checks` fields:

- `check`
- `category`
- `status`
- `evidence_reason`
- `risk_or_warning`
- `source_artifact_references`

Allowed `status` values:

- `pass`
- `warning`
- `fail`
- `not_evaluated`

`review_checks.result` rules:

- `result` is a response/reload-time derived API field.
- Do not add a DB column for `result` unless deterministic reconstruction is
  proven impossible.
- If `status != "not_evaluated"`, `result` must be non-empty and use stable
  keys for that check.
- If `status == "not_evaluated"`, `result` may be empty only when
  `evidence_reason` names the unavailable input.
- Tests must assert stable result keys and at least one non-trivial value for
  every evaluated check.

### Response Surface Rules

Detail/reload responses:

- may reconstruct full action rows from persisted artifacts
- may reconstruct full `review_checks.result`
- may include traceable text summaries derived from persisted warnings,
  caveats, or explicitly persisted run text fields already serialized on that
  same response surface

List/summary responses:

- must be summary-only when heavy artifacts are omitted
- must not expose `buy_candidates`, `sell_or_avoid`, or `watch` rows derived
  from omitted full `signals`
- must not expose derived text prose from omitted warnings, caveats, diagnostic
  samples, or source text
- must not expose any value derived from omitted signals, warnings, comparison
  caveats, diagnostic samples, or source text
- evaluated check results and hidden-derived counts must be omitted or replaced
  with omission-only placeholders
- default safe behavior for `include_artifacts=False` on a successful run:
  action lists are empty, `state` is `no-opinion`, and `state_reason` or
  `evidence_limitations` explains that detail artifacts are omitted and detail
  reload is required for row-level opinion review
- non-successful summary responses retain the downgrade matrix state
  `do-not-adopt` while also explaining that detail artifacts are omitted

### Required Local Methods

Implement these checks locally. Do not import external runtimes.

#### Jesse-style checks

Latest signal definition for all Jesse-style checks and viable action rows:

- The latest persisted signal row is selected per symbol by the maximum
  parseable `date` value in persisted `signals`.
- Persisted list order must not decide which signal row is latest when dates
  differ.
- A row without a parseable `date` must not satisfy row-specific
  latest-date traceability for a viable populated opinion row.
- `invalid_row_count` includes rows without a symbol, rows without a parseable
  date, rows outside an available declared run universe, and selected latest
  rows without a finite numeric `score` or `position`.
- Focused tests must include unsorted multi-date signal rows for the same
  symbol and prove older rows do not drive action rows, bucket counts, or
  `parameter_sensitivity`.

- `strategy_lifecycle`
  - Must verify request/effective strategy, diagnostics, signals, metrics, and
    opinion generation are present or explicitly limited.
  - `result` must include these fixed boolean keys:
    `request_present`, `effective_strategy_present`, `diagnostics_present`,
    `signals_present`, `metrics_present`,
    `opinion_rows_emitted_or_limited`.
  - `pass` requires all result booleans to be `true`.

- `signal_to_position`
  - Must inspect latest persisted signal rows.
  - Must classify latest symbol rows by positive, negative, or flat position.
  - Must verify rows used for action lists have numeric `score` and `position`.
  - `result` must include:
    `checked_symbol_count`, `positive_count`, `negative_count`, `flat_count`,
    `invalid_row_count`.

- `backtest_report_discipline`
  - Missing `metrics` must `fail`.
  - Preserve means the check result reports comparison caveat count, references
    the comparison caveat artifact family when caveats exist, reports
    `threshold_policy_version_present` and `price_basis_version_present`, and
    reports whether the research-only boundary is present.
  - Research-only boundary means the artifact remains `manual_adoption_only`
    and does not contain execution or personalized-advice language.
  - If `threshold_policy_version_present`, `price_basis_version_present`, or
    `research_only_boundary_present` is false, status must not be `pass`.
  - `result` must include:
    `metric_keys`, `caveat_count`,
    `threshold_policy_version_present`, `price_basis_version_present`,
    `research_only_boundary_present`.

- `robustness`
  - Must inspect validation metrics, baselines, warnings, and comparison
    caveats.
  - Validation object presence alone must not `pass`.
  - Validation present with empty metrics must not `pass`.
  - Any blocker comparison caveat must not `pass`.
  - For this check, blocker caveat means any persisted caveat tied to
    non-success status, `artifact_completeness != "complete"`, or an explicit
    blocking/non-comparable marker.
  - Missing baselines must be visible as `warning` or `not_evaluated`; it must
    not be hidden under `pass`.
  - `result` must include:
    `validation_metric_keys`, `baseline_keys`, `warning_count`,
    `blocker_caveat_count`.

- `parameter_sensitivity`
  - Must compute provisional local sensitivity scenarios when persisted signals
    include at least one latest symbol row with numeric `score` and `position`,
    and either persisted `threshold > 0` or persisted `top_n >= 1` exists.
  - If persisted signals exist but no latest symbol row has numeric `score` and
    numeric `position`, status must be `not_evaluated` and `evidence_reason`
    must name the invalid signal rows.
  - Base candidate symbols are the latest persisted signal rows whose
    `position > 0`.
  - Scenario outputs are observational only. They must not change `state`,
    `buy_candidates`, `sell_or_avoid`, or `watch`; they may appear only in
    `review_checks.result` unless another independent gate downgrades the
    opinion.
  - Threshold scenarios:
    - strict threshold = persisted `threshold * 1.25`
    - loose threshold = persisted `threshold * 0.75`
    - skip threshold scenarios with reason when `threshold` is missing or
      `threshold <= 0`
  - Top-n scenarios:
    - `top_n - 1` only when `top_n > 1`
    - `top_n + 1` capped by available latest-symbol count
    - top-n scenarios select symbols by descending latest numeric `score`
    - skip top-n scenarios with reason when `top_n` is missing
  - If only threshold or only `top_n` exists, compute the available scenario
    family and list skipped scenarios.
  - It may be `not_evaluated` only in these cases:
    - signal artifact is missing or the persisted signal list is empty
    - persisted signals exist, but no latest row has numeric `score` and
      numeric `position`
    - at least one latest numeric signal row exists, but (`threshold` is
      missing or `threshold <= 0`) and (`top_n` is missing or `top_n < 1`)
  - Any other partial input state must compute the available scenario family
    and list the unavailable scenario family under `skipped_scenarios`.
  - `result` must include:
    `base_candidate_symbols`, `scenario_candidate_counts`,
    `stable_symbols`, `changed_symbols`, `provisional_policy`,
    `skipped_scenarios`.

#### UZI-style self-review gates

- `evidence_traceability`
  - A viable populated row must include row-specific `evidence_reason` plus at
    least one row-driving signal reference for that row's symbol and selected
    latest date.
  - If `source_artifact_references` remain artifact/field only, shared
    family-level references may support traceability but do not alone satisfy
    traceability for viable rows.
  - Status must be computed from the actual row references. It must not be
    `pass` only because `rows` is non-empty.

- `risk_present`
  - A generic research-only disclaimer is insufficient for viable rows.
  - Each viable row's `risk_or_warning` must be one of these exact evidence
    categories:
    - persisted warning/caveat, naming the warning text or caveat code/severity
      and referencing `warnings` or `comparison_caveats`
    - persisted artifact risk, naming the artifact family and observed risk
      value, such as stale freshness risk, blocker caveat, unavailable source
      audit, or missing validation/baseline evidence
    - checked no-warning result, stating that persisted `warnings` and
      `comparison_caveats` were checked and both counts are zero, while still
      preserving the manual-adoption boundary
  - Status must be computed from each viable row's `risk_or_warning` and
    supporting references. It must not be `pass` only because `rows` is
    non-empty.

- `invalidation_present`
  - A static invalidation template reused for every row is insufficient for
    viable rows.
  - Each viable row must name at least one concrete invalidation family visible
    in persisted artifacts, such as newer data/run availability, warnings,
    caveats, staleness, or missing supporting artifacts.
  - Status must be computed from each viable row's `invalidation_note` and
    supporting references. It must not be `pass` only because `rows` is
    non-empty.

- `manual_adoption_boundary`
  - Must pass only when `manual_adoption_only` is true and opinion-facing text
    does not imply execution, order routing, automatic rebalancing, account
    control, or personalized advice.
  - Must inspect `state_reason`, row `evidence_reason`, row
    `risk_or_warning`, row `invalidation_note`, and review-check copy.
  - Negative tests must cover wording variants in opinion-facing text,
    including `execution-ready`, `order routing`, `automatic rebalance` or
    `automatic rebalancing`, `broker routing`, `account control`, and
    `personalized investment advice`.

- `insufficient_evidence_gate`
  - Stale means persisted freshness-risk fields or explicit freshness caveats
    are present.
  - Required row-driving artifacts for a viable row are:
    - latest persisted signal row for that row's symbol and selected latest
      date
    - numeric signal `score`
    - numeric signal `position`
    - present metrics artifact
    - present model diagnostics artifact
    - `artifact_completeness == "complete"`
    - every artifact family named by that row's `evidence_reason`,
      `risk_or_warning`, `invalidation_note`, or `source_artifact_references`
  - Downgrade matrix:
    - non-successful run -> `do-not-adopt`
    - successful run with `artifact_completeness != "complete"` ->
      `no-opinion`
    - successful run with stale evidence as defined above -> `no-opinion`
    - successful run missing required row-driving artifacts as defined above ->
      `no-opinion`
    - any row that depends on an unavailable or `not_evaluated` required
      artifact must not be emitted as viable

Self-review failures must affect `state`, `state_reason`, or
`evidence_limitations`; they must not be informational labels only.

#### a-stock/OpenBB-style source audit

- `source_artifact_audit`
  - Must distinguish these evidence families:
    - config/fallback metadata present
    - raw-source/provider/parser audit metadata unavailable
  - This goal must not add new raw-source/provider/parser persistence fields.
  - For this goal, raw-source/provider/parser audit metadata is always
    unavailable because current persisted research-run fields do not expose
    provider/source name, parser version, fetch status, fetch timestamp, or a
    stable persisted raw-ingest audit reference.
  - `config_sources` and `fallback_audit` count only as config/fallback
    metadata. They must not be treated as raw/provider/parser audit coverage.
  - `source_artifact_audit` must not `pass` in this goal.
  - If config/fallback metadata exists, status must be `warning` and `result`
    must mark config/fallback present and raw/provider/parser unavailable.
  - If neither `config_sources` nor `fallback_audit` is present, status must be
    `not_evaluated` and `result` must name `config_sources` and
    `fallback_audit` as missing inputs.
  - Do not add provider abstraction, US daily provider selection, or TW/US
    comparison semantics. Future US daily boundaries may appear only as
    limitation/audit wording until `TBD-PHASE-005` is accepted.

#### FinGPT-style evidence summary

- `text_evidence_summary`
  - May summarize only persisted warnings, comparison caveats, or explicitly
    persisted run text fields already serialized on that same response surface.
  - Must be `not_evaluated` when no traceable source text exists.
  - Must not generate trade decisions, advice, or unsupported prose.
  - `result` must include:
    `warning_count`, `caveat_count`, `source_text_count`, `summary_text`,
    `source_artifact_references`.
  - `summary_text` is allowed only on detail/reload responses.
  - Every sentence in `summary_text` must be attributable to persisted warning,
    caveat, or source text that is already present on that response surface.
  - List/summary responses must not emit derived text evidence prose.

### Acceptance Criteria

- [ ] AC-1: Existing opinion action-list contract is preserved
  Given a complete successful persisted research run
  When detail/reload returns `opinion_artifact`
  Then it includes `state`, `state_reason`, `manual_adoption_only`,
  `evidence_limitations`, `buy_candidates`, `sell_or_avoid`, `watch`, and
  `review_checks`
  Evidence: contract/service/API test plus manual check against
  `SPEC-OPINION-001`

- [ ] AC-2: Populated action rows remain traceable
  Given a detail/reload opinion artifact with populated action rows
  When each row is inspected
  Then each row includes `symbol`, `model_score`, `position_signal`,
  `evidence_reason`, `risk_or_warning`, `invalidation_note`, and non-empty
  row-specific `source_artifact_references`
  Evidence: focused domain/API test plus manual check against
  `SPEC-OPINION-002`

- [ ] AC-3: `review_checks.result` is a stable API contract field
  Given any produced `review_checks` item
  When `status != "not_evaluated"`
  Then `result` is non-empty, serialized by API responses, and contains stable
  keys for that check
  Evidence: contract/API/repository test

- [ ] AC-4: Jesse `strategy_lifecycle` has fixed result semantics
  Given complete persisted request, strategy, diagnostics, signals, and metrics
  When `strategy_lifecycle` is evaluated
  Then its result includes all fixed lifecycle booleans and can `pass` only when
  they are all true
  Evidence: focused domain test

- [ ] AC-5: Jesse `signal_to_position` computes bucket counts
  Given persisted unsorted multi-date signal rows with positive, negative,
  flat, and invalid latest rows
  When `signal_to_position` is evaluated
  Then its result reports checked, positive, negative, flat, and invalid counts
  from each symbol's latest persisted `date`, without using older rows or
  emitting invalid rows as viable action rows
  Evidence: focused domain/repository test

- [ ] AC-6: Jesse `backtest_report_discipline` validates metrics and policy
  context
  Given persisted metrics, caveats, and version/policy metadata
  When `backtest_report_discipline` is evaluated
  Then its result reports metric keys, caveat count, threshold policy presence,
  price basis presence, and research-only boundary presence; missing metrics or
  missing required policy/boundary metadata prevents `pass`
  Evidence: focused domain test

- [ ] AC-7: Jesse `robustness` does not false-pass
  Given validation is present but metrics are empty, baselines are missing, or a
  blocker caveat exists
  When `robustness` is evaluated
  Then validation presence alone does not produce `pass`, and the limitation is
  reflected in status and result
  Evidence: focused test covering validation-present-but-caveated behavior

- [ ] AC-8: Jesse `parameter_sensitivity` is computed when inputs exist
  Given persisted unsorted multi-date signals plus effective threshold or
  `top_n`
  When `parameter_sensitivity` is evaluated
  Then available provisional scenarios are computed, skipped scenarios include
  reasons, latest rows are selected by each symbol's maximum persisted `date`,
  and `not_evaluated` is used only for the three method-defined no-input cases
  Evidence: focused domain/repository test

- [ ] AC-9: UZI row evidence, risk, and invalidation gates affect viability
  Given a viable-looking populated row lacks row-specific evidence, concrete
  risk, or concrete invalidation family
  When self-review gates are evaluated
  Then the relevant check fails or warns from the actual row fields and the
  artifact does not remain silently `viable`; `state`, `state_reason`, or
  `evidence_limitations` changes
  Evidence: negative focused tests for missing row-specific signal reference,
  generic risk disclaimer, and static invalidation template

- [ ] AC-10: Manual adoption boundary scans opinion-facing text
  Given opinion-facing text fields are produced
  When `manual_adoption_boundary` is evaluated
  Then the check fails if any field implies execution, order routing, automatic
  rebalancing, broker routing/account control, or personalized investment advice,
  including review-check copy and wording variants such as `execution-ready`
  Evidence: focused negative tests plus manual diff review

- [ ] AC-11: Insufficient evidence uses the downgrade matrix
  Given a non-successful run, partial/metadata-only/stale artifacts, missing
  row-driving evidence, or a row depending on unavailable required artifacts
  When `opinion_artifact` is produced
  Then the artifact follows the documented downgrade matrix and does not emit a
  viable row from unavailable evidence
  Evidence: focused repository/domain tests

- [ ] AC-12: Source/provider audit is honest
  Given only `config_sources` or `fallback_audit` exists, or neither exists
  When `source_artifact_audit` is evaluated
  Then raw-source/provider/parser audit is marked unavailable and the check does
  not `pass`; when neither exists, `result` names missing `config_sources` and
  `fallback_audit`; this goal does not add new raw-source/provider/parser
  persistence fields to make the check pass
  Evidence: focused test plus manual check against a-stock/OpenBB promotion
  criteria

- [ ] AC-13: Text evidence summary stays traceable
  Given persisted warnings or comparison caveats exist on a detail/reload
  response
  When `text_evidence_summary` is evaluated
  Then result counts and any summary text are traceable to those persisted
  warning, caveat, or explicitly persisted run-text artifacts on that same
  response surface
  Evidence: focused test

- [ ] AC-14: No source text means text evidence is not evaluated
  Given no persisted warnings, caveats, or source text exist on the response
  surface
  When `text_evidence_summary` is evaluated
  Then status is `not_evaluated`, result does not invent prose, and the reason
  names the missing input; non-detail/non-reload surfaces omit or empty
  `summary_text`
  Evidence: focused test

- [ ] AC-15: Detail reload reconstructs full opinion sections
  Given a research run has already been persisted
  When the detail/reload path returns the run
  Then action lists and all evaluated `review_checks.result` values are
  reconstructed from persisted artifacts without latest-response memory
  Evidence: repository/API roundtrip test

- [ ] AC-16: List/summary responses do not leak hidden heavy artifacts
  Given `include_artifacts=False` omits full signals, diagnostic samples, or
  source text
  When the list/summary path returns `opinion_artifact`
  Then action lists are empty, hidden-derived prose is absent, hidden-derived
  counts and evaluated check results are omitted or omission-only, and the state
  or limitations explain that detail reload is required for row-level opinion
  review
  Evidence: repository/API list test replacing the current shallow expectation

- [ ] AC-17: Current shallow implementation would fail new or revised tests
  Given the current shallow implementation that only emits names/statuses
  When the new or revised focused tests are considered
  Then at least one test would fail before the fix, and the completion report
  names that test and protected behavior
  Evidence: test name and assertion summary in final report

- [ ] AC-18: No execution or dependency creep
  Given backend opinion expansion is implemented
  When API contracts, code paths, dependencies, and touched docs are inspected
  Then they do not add or imply frontend workflow expansion, broker routing,
  live orders, automatic rebalancing, account control, personalized investment
  advice, US provider implementation, provider abstraction, adaptive/RL control,
  crypto trading behavior, or external runtime adoption
  Evidence: manual diff/dependency review against `GATE-P2-004`,
  `GATE-P2-005`, and `docs/deferred-feature-plan.md`

- [ ] AC-19: Required new files are visible in completion evidence
  Given the implementation adds or depends on a new source or goal file
  When completion evidence is reported
  Then `git status --short` is reviewed and every required new file, including
  `backend/research/domain/opinion.py` and `GOAL.md` if still present, is either
  tracked by git or explicitly listed as an untracked required file in the
  final files-touched report
  Evidence: `git status --short`, `git ls-files` or equivalent file-status
  inspection, and final files-touched summary

### Verification Plan

Run the narrowest focused backend checks that cover the changed contract,
domain/service, repository, and API paths:

```bash
.venv/bin/python -m pytest \
  tests/research/test_runs.py \
  tests/research/test_run_repository.py \
  tests/research/test_research_api.py
```

Also run:

```bash
git diff --check
```

Runtime completion check:

- the focused pytest command exits `0`
- `git diff --check` exits `0`
- file-status audit confirms no required new file is omitted from completion
  evidence
- manual audit confirms AC-1 through AC-19 and scope boundaries

Durable runtime evidence required:

- exact commands
- exit codes
- reached/skipped attempt ledger
- focused output excerpts sufficient to prove the decisive result
- file-status output or equivalent statement covering required new files

Completion audit source:

- current repo diff
- focused test output
- `docs/research-spec.md`
- `docs/validation-gates.md`
- `docs/decision-register.md`
- `docs/deferred-feature-plan.md`
- this `GOAL.md`

### Stop Or Report Blocked

Stop and report blocked if:

- the implementation cannot preserve the existing `opinion_artifact`
  action-list contract
- computed method results require artifacts that are not currently persisted
  and cannot be reconstructed safely
- deterministic reload requires a DB migration whose tradeoff is not justified
  by the docs
- focused tests cannot run after one environment/tooling retry
- the same blocker repeats for three consecutive attempts
- completion would require frontend, broker/live execution, portfolio control,
  US provider work, provider abstraction, adaptive/RL control, crypto runtime
  behavior, or an external dependency
- checked docs conflict about acceptance or scope

If a method cannot be evaluated from current artifacts, do not invent data.
Return `not_evaluated` with a specific reason and ensure the acceptance
criteria state whether that blocks completion.

### Done Condition

The goal is complete only when backend code and tests satisfy AC-1 through
AC-19, the implementation preserves existing action-list behavior,
`review_checks.result` is a stable response/reload contract, method checks
produce concrete results where inputs exist, self-review gates affect
viability, source/provider audit is honest, text evidence stays traceable,
list/detail artifact boundaries are safe, focused verification evidence is
surfaced, required new files are visible in completion evidence,
`git diff --check` passes, and the final manual audit confirms the change stays
within backend-only Phase 2 opinion expansion.
