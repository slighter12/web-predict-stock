# Domain Docs

## Before exploring

- Read root [`CONTEXT.md`](../../CONTEXT.md) for the canonical vocabulary.
- Read [`docs/adr/README.md`](../adr/README.md), then the ADRs that affect the
  area you are touching. ADRs are the source of truth for what this product is,
  where its boundaries are, and why the code looks the way it does.
- Check [`docs/open-decisions.md`](../open-decisions.md) before assuming a
  policy exists. An entry there means **no decision has been made**. Do not
  treat a listed gap as a decision, and do not close one by picking a value.
- For product-direction, roadmap, phase-planning, scope-review, or drift work,
  read [`docs/review-checklist.md`](../review-checklist.md) first.

## Layout

Single-context repo: root `CONTEXT.md` plus system-wide ADRs under `docs/adr/`.
There is no `CONTEXT-MAP.md` and no context-local ADR directory.

The three decision files answer three different kinds of question about the same
thing and do not overlap — a glossary entry says what a term *means*, a spec
says what it must *satisfy*, an ADR says why it was *decided*. See ADR-0001.

Normative behavior lives in `docs/research-spec.md` and
`docs/validation-gates.md`; dependency rules live in
`docs/backend-architecture.md`.

## Consumer rules

- Use the glossary's canonical terms and avoid the synonyms listed under
  `_Avoid_` in new and edited text.
- `_Avoid_` constrains **prose that names the concept**. It does not constrain
  identifiers, persisted field names, quoted UI strings, or standard statistical
  terms used in their ordinary sense — a sentence about `warnings` the artifact
  field, or about out-of-sample skill as a statistical claim, is not a violation.
  Rename the concept in prose; never rename a field to satisfy this file.
- `tests/docs/test_glossary_consistency.py` enforces the checkable part of
  `CONTEXT.md`: every multi-word `_Avoid_` entry plus a few distinctive single
  words. The remaining single words are ordinary English and stay advisory —
  they are guidance for a writer, not a guarantee that anything checks them.
- The only remaining exemptions name real frontend surfaces and are resolved by
  the pending frontend rewrite, not here: the `Start Baseline Study` button text
  quoted by `GATE-V1-002`, and the `Experiment Builder` / `Experiments` surfaces
  named in `README.md` and `docs/implementation-status.md`. Everything else in
  `docs/` uses the canonical terms.
- Define a term by its identity, ownership, and boundaries. Do not copy field
  lists or lifecycle, storage, caching, or reconstruction policy from specs and
  ADRs. A derivation relationship belongs in the glossary only when it is
  necessary to distinguish the term from a neighboring concept.
- Reconsider invented terminology before adding it. Use `domain-modeling` only
  for a real domain gap.
- After editing documentation, run
  `.venv/bin/python -m pytest -q tests/docs/test_glossary_consistency.py`. It
  guards canonical terms and the framing ADR-0005 superseded.
- Surface conflicts with existing ADRs instead of silently overriding them. If
  an ADR is wrong, propose changing the ADR.
- A `proposed` ADR is a direction, not a commitment. Do not treat it as
  authorization to build.
