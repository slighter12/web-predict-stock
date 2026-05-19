# AGENTS.md - Baseline Rules

These rules apply to all tasks in this repo unless a more specific policy or
skill overrides them.

- Language: chat in Traditional Chinese; repo artifacts in English; never
  translate identifiers or config; Chinese UI copy only if a specific policy
  requires it.
- Ambiguity: ask when requirements are unclear or conflicting; do not guess.
- Execution: do not run programs or add tests unless asked or required; include
  a manual verification checklist; note runtime risks/assumptions when relevant.
- Changes and output: keep changes minimal; no refactors, public API renames, or
  new dependencies unless asked; provide a concise change summary plus
  env/config or migration notes when relevant.
- Review routing: when the user asks to review current changes or whether
  current changes are reasonable without explicitly requesting a full code
  review, use `change-sanity-review`; keep it read-only, bounded, and
  diff-centered. Do not invoke provider-native review commands, broad test
  suites, or domain skills unless explicitly requested or clearly required by
  the focused risk.

## Product Strategy Routing

Codex does not reliably auto-discover project-local skill files under
`.codex/skills/`. This section is the Codex bridge for the
`quant-product-strategy-review` skill.

Use the project-local `quant-product-strategy-review` skill before reading long
project docs when the user asks for any of the following:

- product direction or product strategy
- roadmap, phase planning, or next-stage prioritization
- scope review or whether a proposal is drifting
- CEO/PM-style product review
- whether docs and implementation direction still match the intended product

For those tasks, load
`.codex/skills/quant-product-strategy-review/references/product-compass.md`
first, then use README, goals, specs, plans, status, and decision docs as
evidence. Do not start by flattening every long markdown file into a new product
interpretation.

Do not force this skill onto ordinary implementation, bugfix, test, commit, or
code-review tasks unless the user explicitly asks for product strategy review.

## Routing Model

- Rules: apply baseline behavior, language, safety, and output constraints.
- Skills: use reusable policies and workflows when the request matches a skill
  description or explicitly names a skill.
- Agents: suggest sub-agents only when the split is concrete, useful, and worth
  the coordination/token cost; keep high-cost roles such as `oracle` explicit.
- Hooks: treat hooks as deterministic guardrails only; they do not replace
  rules, skills, agents, sandboxing, or permission prompts.
