"""Guard the documentation against drift that reviews keep missing.

`docs/adr/0006-bounded-contexts-with-enforced-layering.md` argues that a rule
living only in a document erodes silently, and that the fix is to make it fail a
test run. These checks apply that reasoning to the documentation itself, in the
same shape as `tests/architecture/test_backend_import_boundaries.py`: rules and
exemptions are module-level constants, so every exemption is named and countable
rather than ambient.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTEXT = ROOT / "CONTEXT.md"
ADR_INDEX = ROOT / "docs" / "adr" / "README.md"
SCANNED = (
    [ROOT / "README.md", CONTEXT]
    + sorted((ROOT / "docs").rglob("*.md"))
)

# --- Test A: framing superseded by ADR-0005 ---------------------------------
#
# ADR-0005 replaced "regression is primary, direction confirms" with "direction
# is the admission gate, magnitude is the ranking". Matching a bare `confirm`
# would flag unrelated prose (broker manual-confirmation gates, verification
# steps), so `confirm` only counts when it sits near the direction model.

_NEAR = r"(?:direction|classification|classifier)"

# Retired phrases are declared by the ADR that retires them, in its
# `supersedes_language:` frontmatter, and collected here. Nothing about a
# specific decision is hardcoded in this file: a new ADR that retires an older
# wording is guarded the moment it declares the wording, without editing tests.
#
# An ADR author writes a plain phrase. This module decides how to match it: a
# phrase built around `confirm` is matched only near the direction model, so the
# legitimate broker manual-confirmation gates and verification steps elsewhere
# in docs/ never trip it.

ALWAYS_DECLARE_MARKERS = ("replaces", "supersede", "no longer", "retired")

# (path relative to repo root, substring that identifies the exempt line)
FRAMING_EXEMPTIONS = (
    # ADR-0005 must describe the framing it replaces.
    ("docs/adr/0005-long-only-direction-gate-magnitude-ranking.md", "This replaces the earlier framing"),
    ("docs/adr/0005-long-only-direction-gate-magnitude-ranking.md", "direction as a confirmation step"),
    # CONTEXT.md defines the term and lists the avoided synonym.
    ("CONTEXT.md", "An admission decision, not a confirmation"),
    ("CONTEXT.md", "_Avoid_: direction confirmation"),
    # A persisted config field, not the model's role.
    ("docs/research-spec.md", "confirmation thresholds"),
)


def _adr_files() -> list[Path]:
    return sorted((ROOT / "docs" / "adr").glob("[0-9]*.md"))


def _adr_index_rows() -> list[tuple[str, str, str]]:
    rows = []
    for _, line in _lines(ADR_INDEX):
        match = re.fullmatch(r"\|\s*\[(\d+)\]\(([^)]+)\)\s*\|.*\|\s*([^|]+?)\s*\|", line)
        if match:
            rows.append(tuple(part.strip() for part in match.groups()))
    return rows


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    block = text.split("---\n", 2)[1]
    fields = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def _retired_phrases() -> list[str]:
    phrases = []
    for path in _adr_files():
        declared = _frontmatter(path).get("supersedes_language", "")
        if not declared or declared.lower() == "none":
            continue
        phrases.extend(p.strip() for p in declared.split(",") if p.strip())
    return phrases


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match a retired phrase, loosening `confirm` wording near the direction model."""
    if "confirm" in phrase.lower():
        head = re.escape(phrase.lower().split("confirm")[0].strip())
        if head in {"", re.escape("")}:
            return re.compile(rf"confirm\w*\W+(?:\w+\W+){{0,6}}{_NEAR}|{_NEAR}\W+(?:\w+\W+){{0,6}}confirm\w*", re.I)
        return re.compile(rf"{_NEAR}\W+(?:\w+\W+){{0,6}}confirm\w*|confirm\w*\W+(?:\w+\W+){{0,6}}{_NEAR}", re.I)
    return re.compile(re.escape(phrase), re.I)


# --- Test B: glossary `_Avoid_` synonyms ------------------------------------
#
# Only part of `CONTEXT.md`'s `_Avoid_` lists can be checked mechanically. A
# multi-word entry is specific enough that a hit is almost certainly the
# concept; so are a few distinctive single words. The rest -- `market`, `data`,
# `universe`, `coverage`, `sample`, `score`, `prediction`, `reference`,
# `control` and friends -- are ordinary English that appears constantly in
# legitimate compounds, and they are NOT guarded here. They remain advisory
# guidance in CONTEXT.md; do not assume this test covers them.

ENFORCED_SINGLE_WORDS = ("experiment", "study", "ticker", "alpha", "forecast", "disclaimer")

# Every exemption below names a real frontend surface, resolved by the pending
# frontend rewrite rather than by renaming prose.
SYNONYM_EXEMPTIONS = (
    ("docs/validation-gates.md", "Start Baseline Study"),
    ("docs/agents/domain.md", "Start Baseline Study"),
    ("README.md", "Experiment Builder for the baseline"),
    ("README.md", "builder, experiments, and data diagnostics"),
    ("docs/implementation-status.md", "`Experiment Builder`"),
    ("docs/implementation-status.md", "Start, Experiment Builder, Experiments"),
    ("docs/agents/domain.md", "`Experiment Builder` / `Experiments` surfaces"),
)


def _is_declaration(line: str) -> bool:
    """A frontmatter line declaring retired wording states it, it does not use it."""
    return line.startswith("supersedes_language:")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _lines(path: Path) -> list[tuple[int, str]]:
    return list(enumerate(path.read_text(encoding="utf-8").splitlines(), 1))


def _is_exempt(rel: str, line: str, exemptions: tuple[tuple[str, str], ...]) -> bool:
    return any(rel == path and marker in line for path, marker in exemptions)


def _avoided_terms() -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    current: str | None = None
    for _, line in _lines(CONTEXT):
        heading = re.match(r"^\*\*(.+?)\*\*:$", line)
        if heading:
            current = heading.group(1)
        elif line.startswith("_Avoid_:") and current:
            terms[current] = [w.strip() for w in line[len("_Avoid_:"):].split(",") if w.strip()]
    return terms


def _enforced(synonyms: list[str]) -> list[str]:
    return [
        s for s in synonyms
        if " " in s or "-" in s or s.lower() in ENFORCED_SINGLE_WORDS
    ]


def test_context_md_parses_into_terms():
    terms = _avoided_terms()
    assert len(terms) >= 20, f"CONTEXT.md parsed only {len(terms)} terms; the format likely changed"
    assert "Direction Gate" in terms
    expected = {
        "Research Track",
        "Technical Research Track",
        "Feature Family",
        "Sentiment Feature Family",
    }
    assert expected <= terms.keys(), (
        "CONTEXT.md is missing canonical glossary entries: "
        + ", ".join(sorted(expected - terms.keys()))
    )


def test_docs_do_not_assert_framing_superseded_by_an_adr():
    patterns = [_phrase_pattern(p) for p in _retired_phrases()]
    assert patterns, "no ADR declares supersedes_language; the framing check is inert"
    violations = []
    for path in SCANNED:
        rel = _relative(path)
        for number, line in _lines(path):
            if _is_declaration(line) or _is_exempt(rel, line, FRAMING_EXEMPTIONS):
                continue
            if any(pattern.search(line) for pattern in patterns):
                violations.append(f"{rel}:{number}: {line.strip()}")
    assert not violations, (
        "Documentation asserts framing an ADR retired via supersedes_language. "
        "Found:\n" + "\n".join(violations)
    )


def test_docs_use_canonical_terms_from_the_glossary():
    enforced = {
        synonym: term
        for term, synonyms in _avoided_terms().items()
        for synonym in _enforced(synonyms)
    }
    violations = []
    for path in SCANNED:
        rel = _relative(path)
        for number, line in _lines(path):
            # CONTEXT.md is the glossary: each `_Avoid_` declaration must name
            # the synonyms it displaces so consumers can avoid them.
            if rel == "CONTEXT.md":
                continue
            if _is_declaration(line) or _is_exempt(rel, line, SYNONYM_EXEMPTIONS):
                continue
            for synonym, term in enforced.items():
                if re.search(rf"\b{re.escape(synonym)}\b", line, re.I):
                    violations.append(f"{rel}:{number}: use '{term}', not '{synonym}': {line.strip()[:80]}")
    assert not violations, (
        "CONTEXT.md canonical terms not used:\n" + "\n".join(violations)
    )


def test_adrs_that_retire_wording_declare_it():
    missing = []
    for path in _adr_files():
        text = path.read_text(encoding="utf-8")
        body = text.split("---\n", 2)[-1].lower()
        if not any(marker in body for marker in ALWAYS_DECLARE_MARKERS):
            continue
        if "supersedes_language" not in _frontmatter(path):
            missing.append(_relative(path))
    assert not missing, (
        "These ADRs retire something in their body but do not declare which wording "
        "they retire. Add `supersedes_language:` listing the retired phrases, or "
        "`supersedes_language: none` when no quotable phrase is retired:\n"
        + "\n".join(missing)
    )


def test_adr_index_matches_files_and_frontmatter_status():
    rows = _adr_index_rows()
    indexed = {(number, filename): status for number, filename, status in rows}
    files = _adr_files()
    expected = {}
    for path in files:
        number, _, _ = path.name.partition("-")
        expected[(number, path.name)] = _frontmatter(path).get("status", "")

    problems = []
    if len(indexed) != len(rows):
        problems.append("ADR index contains duplicate rows")
    index_numbers = [number for number, _, _ in rows]
    if len(set(index_numbers)) != len(index_numbers):
        problems.append("ADR index contains duplicate numbers")
    file_numbers = [path.name.partition("-")[0] for path in files]
    if len(set(file_numbers)) != len(file_numbers):
        problems.append("ADR files contain duplicate numbers")

    for key in sorted(set(indexed) | set(expected)):
        if key not in indexed:
            problems.append(f"missing from ADR index: {key[0]} -> {key[1]}")
            continue
        if key not in expected:
            problems.append(f"ADR index points to missing file: {key[0]} -> {key[1]}")
            continue
        index_status = indexed[key]
        file_status = expected[key]
        if not file_status:
            problems.append(f"ADR has no frontmatter status: {key[1]}")
        elif index_status != file_status:
            problems.append(
                f"status mismatch for {key[1]}: index={index_status!r}, frontmatter={file_status!r}"
            )

    assert not problems, "ADR index, files, and frontmatter status have drifted:\n" + "\n".join(problems)


# --- Test C: normative enumerations live in one file ------------------------
#
# `SPEC-RUN-001` (persisted artifacts) and `SPEC-COMP-001` (comparison
# dimensions) are authoritative lists. Restating one elsewhere is how five
# copies of SPEC-RUN-001 came to disagree with it and with each other. Other
# docs reference the spec ID; they do not re-enumerate.
#
# WHY ONLY TWO LISTS -- this was measured, not assumed. Guarding every
# `### SPEC-*` bullet list produces 71 hits, nearly all false: SPEC-OPINION-001
# lists generic items (`evidence`, `risk`, `direction`, `symbol`), so any
# sentence about opinions matches four of them, and even README's opening
# paragraph was flagged. Tightening to whole-phrase matching instead collapses
# to 1 hit and misses every real restatement, because a paraphrase writes
# "diagnostics" where the spec writes "model diagnostics". Only lists whose
# vocabulary is distinctive *in combination* survive this trade-off.
#
# So: partial restatements of the other SPEC lists are NOT guarded. That is the
# measured boundary of this technique, not an oversight. Widening it produces a
# test people delete rather than a test that finds bugs.

SPEC = ROOT / "docs" / "research-spec.md"
GUARDED_LISTS = (("SPEC-RUN-001", "SPEC-RUN-002"), ("SPEC-COMP-001", "SPEC-COMP-002"))
ENUMERATION_THRESHOLD = 4

# Head words too generic to distinguish one list from ordinary prose.
_IGNORED_HEADS = {"metrics", "range", "family"}

ENUMERATION_EXEMPTIONS = (
    # Builder inputs, not comparison dimensions.
    ("docs/implementation-status.md", "baseline workflow creates research runs"),
    # The workflow diagram, not a list of comparison dimensions.
    ("docs/project-goals.md", "Dataset -> Features -> Prediction Task"),
    # About result ordering, not about which dimensions are shown.
    ("docs/validation-gates.md", "`KPI-COMP-003`"),
)


def _spec_list(start: str, end: str) -> list[str]:
    section = SPEC.read_text(encoding="utf-8").split(f"### {start}", 1)[1].split(f"### {end}", 1)[0]
    return [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]


def _heads(items: list[str]) -> dict[str, list[str]]:
    return {
        item: [w for w in re.split(r"[ /]|\bor\b", item) if len(w) > 3 and w not in _IGNORED_HEADS]
        for item in items
    }


def test_guarded_spec_lists_parse():
    for start, end in GUARDED_LISTS:
        items = _spec_list(start, end)
        assert len(items) >= 6, f"{start} parsed as {items}; spec format likely changed"


def test_normative_spec_lists_are_not_restated():
    guarded = {start: _heads(_spec_list(start, end)) for start, end in GUARDED_LISTS}
    violations = []
    for path in SCANNED:
        rel = _relative(path)
        if rel in {"docs/research-spec.md", "CONTEXT.md"}:
            continue
        for number, line in _lines(path):
            if _is_exempt(rel, line, ENUMERATION_EXEMPTIONS):
                continue
            for spec_id, heads in guarded.items():
                named = {
                    item
                    for item, words in heads.items()
                    if any(re.search(rf"\b{re.escape(w)}", line, re.I) for w in words)
                }
                if len(named) >= ENUMERATION_THRESHOLD:
                    violations.append(
                        f"{rel}:{number}: names {len(named)} {spec_id} items; "
                        f"reference the spec instead: {line.strip()[:64]}"
                    )
                    break
    assert not violations, (
        "Reference the spec ID instead of restating its list; every previous "
        "restatement drifted apart from the spec:\n" + "\n".join(violations)
    )
