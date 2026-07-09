from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

OPINION_ARTIFACT_VERSION = "phase2_opinion_artifact_v1"
OMITTED_DETAIL_LIMITATION = (
    "Detail artifacts are omitted; reload the run detail for row-level opinion review."
)
RAW_PROVIDER_FIELDS = [
    "provider_source_name",
    "parser_version",
    "fetch_status",
    "fetch_timestamp",
    "raw_ingest_audit_ref",
]
PROVISIONAL_POLICY = (
    "Local sensitivity scenarios are observational only and do not change action lists."
)
BOUNDARY_RISK = (
    "Checked no-warning result: persisted warnings and comparison caveats were checked; "
    "manual adoption review is still required."
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _signal_date_key(signal: Mapping[str, Any]) -> str | None:
    value = signal.get("date")
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def _refs(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"artifact": artifact, "field": field} for artifact, field in items]


def _signal_ref(field: str, signal: Mapping[str, Any]) -> dict[str, str]:
    ref = {"artifact": "signals", "field": field}
    if signal.get("symbol") is not None:
        ref["symbol"] = str(signal["symbol"])
    if signal.get("date") is not None:
        ref["date"] = str(signal["date"])
    return ref


def _risk_context(payload: Mapping[str, Any]) -> tuple[str, list[dict[str, str]], str]:
    warnings = [str(item) for item in _as_list(payload.get("warnings"))]
    if warnings:
        return (
            f"Persisted warning: {warnings[0]}",
            _refs(("warnings", "warnings")),
            "warning",
        )

    caveats = [_as_mapping(item) for item in _as_list(payload.get("comparison_caveats"))]
    if caveats:
        caveat = caveats[0]
        code = str(caveat.get("code", "COMPARISON_CAVEAT"))
        severity = str(caveat.get("severity", "blocker"))
        return (
            f"Persisted caveat {code} with severity {severity}.",
            _refs(("comparison_caveats", "comparison_caveats")),
            "caveat",
        )

    return (
        BOUNDARY_RISK,
        _refs(("warnings", "warnings"), ("comparison_caveats", "comparison_caveats")),
        "checked_no_warning",
    )


def _invalidation_context(payload: Mapping[str, Any]) -> tuple[str, list[dict[str, str]], str]:
    if payload.get("stale_mark_days_with_open_positions") or payload.get(
        "stale_risk_share"
    ):
        return (
            "Do not adopt if stale freshness risk remains in persisted run artifacts.",
            _refs(
                ("artifact_completeness", "stale_mark_days_with_open_positions"),
                ("artifact_completeness", "stale_risk_share"),
            ),
            "stale_freshness",
        )
    if _as_list(payload.get("comparison_caveats")):
        return (
            "Do not adopt if persisted comparison caveats still apply.",
            _refs(("comparison_caveats", "comparison_caveats")),
            "comparison_caveats",
        )
    return (
        "Do not adopt if a newer persisted run or newer market data supersedes this signal.",
        _refs(("request_payload", "date_range"), ("signals", "date")),
        "newer_run_or_market_data",
    )


def _latest_signals(payload: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], int]:
    latest_by_symbol: dict[str, Mapping[str, Any]] = {}
    latest_date_by_symbol: dict[str, str | None] = {}
    for item in _as_list(payload.get("signals")):
        signal = _as_mapping(item)
        symbol = signal.get("symbol")
        if not symbol:
            continue
        symbol_key = str(symbol)
        signal_date = _signal_date_key(signal)
        if symbol_key not in latest_by_symbol:
            latest_by_symbol[symbol_key] = signal
            latest_date_by_symbol[symbol_key] = signal_date
            continue
        current_date = latest_date_by_symbol[symbol_key]
        if signal_date is not None and (
            current_date is None or signal_date >= current_date
        ):
            latest_by_symbol[symbol_key] = signal
            latest_date_by_symbol[symbol_key] = signal_date
        elif signal_date is None and current_date is None:
            latest_by_symbol[symbol_key] = signal
    latest = [latest_by_symbol[symbol] for symbol in sorted(latest_by_symbol)]
    invalid_count = sum(
        1
        for item in latest
        if _signal_date_key(item) is None
        or not _is_number(item.get("score"))
        or not _is_number(item.get("position"))
    )
    return latest, invalid_count


def _valid_latest_signals(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    latest, _ = _latest_signals(payload)
    return [
        item
        for item in latest
        if _signal_date_key(item) is not None
        and _is_number(item.get("score"))
        and _is_number(item.get("position"))
    ]


def _action_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    risk, risk_refs, _risk_family = _risk_context(payload)
    invalidation, invalidation_refs, _invalidation_family = _invalidation_context(payload)
    rows: list[dict[str, Any]] = []
    for signal in _valid_latest_signals(payload):
        symbol = str(signal["symbol"])
        signal_date = str(signal["date"])
        rows.append(
            {
                "symbol": symbol,
                "model_score": float(signal["score"]),
                "position_signal": float(signal["position"]),
                "evidence_reason": (
                    f"Latest persisted signal for {symbol} on {signal_date} links "
                    "numeric score to strategy position."
                ),
                "risk_or_warning": risk,
                "invalidation_note": f"{invalidation} Row signal date: {signal_date} for {symbol}.",
                "source_artifact_references": [
                    _signal_ref("score", signal),
                    _signal_ref("position", signal),
                    *_refs(
                        ("model_diagnostics", "model_diagnostics"),
                        ("metrics", "metrics"),
                        ("artifact_completeness", "artifact_completeness"),
                    ),
                    *risk_refs,
                    *invalidation_refs,
                ],
            }
        )
    return rows


def _blocker_caveat_count(payload: Mapping[str, Any]) -> int:
    caveats = [_as_mapping(item) for item in _as_list(payload.get("comparison_caveats"))]
    if payload.get("status") != "succeeded" or payload.get("artifact_completeness") != "complete":
        return len(caveats)
    return sum(
        1
        for caveat in caveats
        if caveat.get("severity") == "blocker"
        or str(caveat.get("code", "")).endswith("_MISSING")
        or str(caveat.get("code", "")).endswith("_ONLY")
    )


def _strategy_threshold(payload: Mapping[str, Any]) -> float | None:
    strategy = _as_mapping(payload.get("effective_strategy")) or _as_mapping(
        _as_mapping(payload.get("request_payload")).get("strategy")
    )
    threshold = strategy.get("threshold")
    return float(threshold) if _is_number(threshold) else None


def _strategy_top_n(payload: Mapping[str, Any]) -> int | None:
    strategy = _as_mapping(payload.get("effective_strategy")) or _as_mapping(
        _as_mapping(payload.get("request_payload")).get("strategy")
    )
    top_n = strategy.get("top_n")
    return int(top_n) if isinstance(top_n, int) and not isinstance(top_n, bool) else None


def _string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_string_values(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_string_values(item))
        return strings
    return [str(value)]


def _manual_boundary_present(*texts: str) -> bool:
    forbidden = (
        "broker routing",
        "broker",
        "execution-ready",
        "execution ready",
        "live order",
        "live orders",
        "automatic rebalance",
        "automatic rebalancing",
        "account control",
        "personalized investment advice",
        "personalized advice",
        "place order",
        "order routing",
    )
    haystack = " ".join(texts).lower()
    return not any(term in haystack for term in forbidden)


def _opinion_texts(
    payload: Mapping[str, Any],
    rows: list[dict[str, Any]],
    checks: list[dict[str, Any]] | None = None,
) -> list[str]:
    texts = [str(payload.get("state_reason", ""))]
    for row in rows:
        texts.extend(
            str(row.get(field, ""))
            for field in ("evidence_reason", "risk_or_warning", "invalidation_note")
        )
    texts.extend(str(item) for item in _as_list(payload.get("warnings")))
    for caveat in _as_list(payload.get("comparison_caveats")):
        texts.extend(_string_values(caveat))
    for check in checks or []:
        texts.extend(
            [
                str(check.get("evidence_reason", "")),
                str(check.get("risk_or_warning", "")),
            ]
        )
        texts.extend(_string_values(check.get("result")))
    return texts


def _check(
    check: str,
    category: str,
    status: str,
    evidence_reason: str,
    risk_or_warning: str,
    source_artifact_references: list[dict[str, str]],
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "category": category,
        "status": status,
        "evidence_reason": evidence_reason,
        "risk_or_warning": risk_or_warning,
        "source_artifact_references": source_artifact_references,
        "result": result or {},
    }


def _row_signal_reference_count(row: Mapping[str, Any]) -> int:
    return sum(
        1
        for ref in _as_list(row.get("source_artifact_references"))
        if _as_mapping(ref).get("artifact") == "signals"
        and _as_mapping(ref).get("symbol") == row.get("symbol")
        and _as_mapping(ref).get("date")
    )


def _row_has_traceable_signal(row: Mapping[str, Any]) -> bool:
    return bool(row.get("evidence_reason")) and _row_signal_reference_count(row) > 0


def _row_has_concrete_risk(
    row: Mapping[str, Any],
    context: tuple[str, list[dict[str, str]], str],
) -> bool:
    refs = {
        _as_mapping(ref).get("artifact")
        for ref in _as_list(row.get("source_artifact_references"))
    }
    text, _context_refs, family = context
    if row.get("risk_or_warning") != text:
        return False
    return (
        (family == "warning" and "warnings" in refs)
        or (family == "caveat" and "comparison_caveats" in refs)
        or (
            family == "checked_no_warning"
            and {"warnings", "comparison_caveats"} <= refs
        )
    )


def _row_has_concrete_invalidation(
    row: Mapping[str, Any],
    context: tuple[str, list[dict[str, str]], str],
) -> bool:
    refs = {
        _as_mapping(ref).get("artifact")
        for ref in _as_list(row.get("source_artifact_references"))
    }
    text, _context_refs, family = context
    if not str(row.get("invalidation_note", "")).startswith(f"{text} Row signal date:"):
        return False
    return (
        (family == "stale_freshness" and "artifact_completeness" in refs)
        or (family == "comparison_caveats" and "comparison_caveats" in refs)
        or (
            family == "newer_run_or_market_data"
            and {"request_payload", "signals"} <= refs
        )
    )


def _summary_checks() -> list[dict[str, Any]]:
    result = {"omitted_for_summary": True}
    return [
        _check(
            check,
            category,
            "not_evaluated",
            "Detail artifacts are omitted from this summary response.",
            "Reload run detail before using opinion checks.",
            _refs(("artifact_completeness", "artifact_completeness")),
            result,
        )
        for check, category in (
            ("strategy_lifecycle", "method"),
            ("signal_to_position", "method"),
            ("backtest_report_discipline", "method"),
            ("robustness", "method"),
            ("parameter_sensitivity", "method"),
            ("evidence_traceability", "self_review"),
            ("risk_present", "self_review"),
            ("invalidation_present", "self_review"),
            ("manual_adoption_boundary", "self_review"),
            ("insufficient_evidence_gate", "self_review"),
            ("source_artifact_audit", "source_provider_audit"),
            ("text_evidence_summary", "evidence_summary"),
        )
    ]


def _parameter_sensitivity(payload: Mapping[str, Any]) -> dict[str, Any]:
    latest, invalid_count = _latest_signals(payload)
    valid = _valid_latest_signals(payload)
    threshold = _strategy_threshold(payload)
    top_n = _strategy_top_n(payload)
    base = sorted(
        str(item["symbol"]) for item in valid if float(item["position"]) > 0
    )
    skipped: list[str] = []
    scenarios: dict[str, set[str]] = {}

    if not latest:
        return {
            "status": "not_evaluated",
            "reason": "Signal artifact is missing or empty.",
            "result": {
                "base_candidate_symbols": [],
                "scenario_candidate_counts": {},
                "stable_symbols": [],
                "changed_symbols": [],
                "provisional_policy": PROVISIONAL_POLICY,
                "skipped_scenarios": ["signals_missing_or_empty"],
            },
        }
    if not valid:
        return {
            "status": "not_evaluated",
            "reason": "Persisted signal rows lack numeric score or position.",
            "result": {
                "base_candidate_symbols": [],
                "scenario_candidate_counts": {},
                "stable_symbols": [],
                "changed_symbols": [],
                "provisional_policy": PROVISIONAL_POLICY,
                "skipped_scenarios": ["invalid_signal_rows"],
            },
        }
    if threshold is None or threshold <= 0:
        skipped.append("threshold_missing_or_non_positive")
    else:
        scenarios["strict_threshold"] = {
            str(item["symbol"]) for item in valid if float(item["score"]) >= threshold * 1.25
        }
        scenarios["loose_threshold"] = {
            str(item["symbol"]) for item in valid if float(item["score"]) >= threshold * 0.75
        }

    ranked = sorted(valid, key=lambda item: float(item["score"]), reverse=True)
    if top_n is None:
        skipped.append("top_n_missing")
    elif top_n < 1:
        skipped.append("top_n_less_than_one")
    else:
        if top_n > 1:
            scenarios["top_n_minus_1"] = {
                str(item["symbol"]) for item in ranked[: top_n - 1]
            }
        else:
            skipped.append("top_n_minus_1_requires_top_n_above_one")
        scenarios["top_n_plus_1"] = {
            str(item["symbol"]) for item in ranked[: min(top_n + 1, len(ranked))]
        }

    if not scenarios:
        return {
            "status": "not_evaluated",
            "reason": "No threshold or top_n scenario inputs are available.",
            "result": {
                "base_candidate_symbols": base,
                "scenario_candidate_counts": {},
                "stable_symbols": [],
                "changed_symbols": [],
                "provisional_policy": PROVISIONAL_POLICY,
                "skipped_scenarios": skipped,
            },
        }

    scenario_sets = list(scenarios.values())
    stable = sorted(set(base).intersection(*scenario_sets)) if base else []
    changed = sorted(set().union(*scenario_sets).symmetric_difference(set(base)))
    return {
        "status": "warning" if invalid_count else "pass",
        "reason": "Local provisional sensitivity scenarios were computed.",
        "result": {
            "base_candidate_symbols": base,
            "scenario_candidate_counts": {
                key: len(value) for key, value in scenarios.items()
            },
            "stable_symbols": stable,
            "changed_symbols": changed,
            "provisional_policy": PROVISIONAL_POLICY,
            "skipped_scenarios": skipped,
        },
    }


def _review_checks(
    payload: Mapping[str, Any],
    rows: list[dict[str, Any]],
    state: str,
    limitations: list[str],
) -> list[dict[str, Any]]:
    metrics = _as_mapping(payload.get("metrics"))
    diagnostics = _as_mapping(payload.get("model_diagnostics"))
    signals = _as_list(payload.get("signals"))
    validation = _as_mapping(payload.get("validation"))
    validation_metrics = _as_mapping(validation.get("metrics"))
    baselines = _as_mapping(payload.get("baselines"))
    caveats = _as_list(payload.get("comparison_caveats"))
    warnings = _as_list(payload.get("warnings"))
    latest, invalid_signal_count = _latest_signals(payload)
    positive = sum(1 for item in _valid_latest_signals(payload) if float(item["position"]) > 0)
    negative = sum(1 for item in _valid_latest_signals(payload) if float(item["position"]) < 0)
    flat = sum(1 for item in _valid_latest_signals(payload) if float(item["position"]) == 0)
    boundary_present = _manual_boundary_present(*_opinion_texts(payload, rows))
    lifecycle = {
        "request_present": bool(_as_mapping(payload.get("request_payload"))),
        "effective_strategy_present": bool(_as_mapping(payload.get("effective_strategy"))),
        "diagnostics_present": bool(diagnostics),
        "signals_present": bool(signals),
        "metrics_present": bool(metrics),
        "opinion_rows_emitted_or_limited": bool(rows) or bool(limitations),
    }
    backtest_result = {
        "metric_keys": sorted(metrics),
        "caveat_count": len(caveats),
        "threshold_policy_version_present": bool(payload.get("threshold_policy_version")),
        "price_basis_version_present": bool(payload.get("price_basis_version")),
        "research_only_boundary_present": boundary_present,
    }
    robust_result = {
        "validation_metric_keys": sorted(validation_metrics),
        "baseline_keys": sorted(baselines),
        "warning_count": len(warnings),
        "blocker_caveat_count": _blocker_caveat_count(payload),
    }
    config_sources_present = bool(_as_mapping(payload.get("config_sources")))
    fallback_audit_present = bool(_as_mapping(payload.get("fallback_audit")))
    source_audit_result = {
        "config_fallback_metadata_present": bool(
            config_sources_present or fallback_audit_present
        ),
        "config_sources_present": config_sources_present,
        "fallback_audit_present": fallback_audit_present,
        "raw_provider_parser_audit_available": False,
        "missing_raw_provider_parser_fields": RAW_PROVIDER_FIELDS,
        "missing_config_fallback_inputs": [
            name
            for name, present in (
                ("config_sources", config_sources_present),
                ("fallback_audit", fallback_audit_present),
            )
            if not present
        ],
    }
    text_sources = warnings + caveats
    summary_text = ""
    if text_sources:
        first = text_sources[0]
        if isinstance(first, Mapping):
            summary_text = str(first.get("label") or first.get("code") or "")
        else:
            summary_text = str(first)
    text_result = {
        "warning_count": len(warnings),
        "caveat_count": len(caveats),
        "source_text_count": len(text_sources),
        "summary_text": summary_text,
        "source_artifact_references": _refs(
            ("warnings", "warnings"), ("comparison_caveats", "comparison_caveats")
        )
        if text_sources
        else [],
    }
    sensitivity = _parameter_sensitivity(payload)
    risk_context = _risk_context(payload)
    invalidation_context = _invalidation_context(payload)
    traceable_row_count = sum(1 for row in rows if _row_has_traceable_signal(row))
    concrete_risk_row_count = sum(
        1 for row in rows if _row_has_concrete_risk(row, risk_context)
    )
    concrete_invalidation_row_count = sum(
        1
        for row in rows
        if _row_has_concrete_invalidation(row, invalidation_context)
    )
    checks = [
        _check(
            "strategy_lifecycle",
            "method",
            "pass" if all(lifecycle.values()) else "fail",
            "Request, effective strategy, diagnostics, signals, metrics, and opinion output were checked.",
            "Missing lifecycle input blocks method confidence."
            if not all(lifecycle.values())
            else "Lifecycle inputs are present for research review.",
            _refs(
                ("request_payload", "request_payload"),
                ("model_diagnostics", "model_diagnostics"),
                ("signals", "signals"),
                ("metrics", "metrics"),
            ),
            lifecycle,
        ),
        _check(
            "signal_to_position",
            "method",
            "pass" if latest and invalid_signal_count == 0 else "warning" if latest else "fail",
            "Latest persisted signal rows were bucketed by position sign.",
            "Invalid latest signal rows were excluded from action rows."
            if invalid_signal_count
            else "Signal buckets are derived from numeric latest rows.",
            _refs(("signals", "signals")),
            {
                "checked_symbol_count": len(latest),
                "positive_count": positive,
                "negative_count": negative,
                "flat_count": flat,
                "invalid_row_count": invalid_signal_count,
            },
        ),
        _check(
            "backtest_report_discipline",
            "method",
            "pass"
            if metrics
            and backtest_result["threshold_policy_version_present"]
            and backtest_result["price_basis_version_present"]
            and boundary_present
            and not caveats
            else "warning"
            if metrics
            else "fail",
            "Metrics, caveat count, version policy, and research-only boundary were checked.",
            "Caveats or missing policy metadata prevent a clean pass."
            if caveats or not metrics
            else "Backtest context is present for research review.",
            _refs(
                ("metrics", "metrics"),
                ("comparison_caveats", "comparison_caveats"),
                ("version_pack", "threshold_policy_version"),
                ("version_pack", "price_basis_version"),
            ),
            backtest_result,
        ),
        _check(
            "robustness",
            "method",
            "pass"
            if validation_metrics and baselines and not robust_result["blocker_caveat_count"]
            else "warning"
            if validation or caveats or warnings or not baselines
            else "not_evaluated",
            "Validation metrics, baselines, warnings, and blocker caveats were checked.",
            "Validation metrics, baselines, or caveats limit robustness confidence.",
            _refs(
                ("validation", "validation"),
                ("baselines", "baselines"),
                ("warnings", "warnings"),
                ("comparison_caveats", "comparison_caveats"),
            ),
            robust_result,
        ),
        _check(
            "parameter_sensitivity",
            "method",
            sensitivity["status"],
            sensitivity["reason"],
            "Sensitivity output is provisional and local.",
            _refs(("signals", "signals"), ("request_payload", "strategy")),
            sensitivity["result"],
        ),
        _check(
            "evidence_traceability",
            "self_review",
            "pass"
            if (rows and traceable_row_count == len(rows)) or state != "viable"
            else "fail",
            "Viable rows were checked for row-specific latest signal references.",
            "Rows without row-specific signal references block viability.",
            _refs(("signals", "signals"), ("artifact_completeness", "artifact_completeness")),
            {
                "row_count": len(rows),
                "row_specific_signal_reference_count": sum(
                    _row_signal_reference_count(row) for row in rows
                ),
                "untraceable_row_count": len(rows) - traceable_row_count,
            },
        ),
        _check(
            "risk_present",
            "self_review",
            "pass"
            if (rows and concrete_risk_row_count == len(rows)) or limitations
            else "fail",
            "Rows were checked for concrete warning, caveat, or no-warning evidence.",
            risk_context[0],
            risk_context[1],
            {
                "row_count": len(rows),
                "concrete_risk_row_count": concrete_risk_row_count,
                "missing_risk_row_count": len(rows) - concrete_risk_row_count,
                "limitation_count": len(limitations),
            },
        ),
        _check(
            "invalidation_present",
            "self_review",
            "pass"
            if (rows and concrete_invalidation_row_count == len(rows)) or limitations
            else "fail",
            "Rows were checked for concrete invalidation families and supporting references.",
            invalidation_context[0],
            invalidation_context[1],
            {
                "row_count": len(rows),
                "concrete_invalidation_row_count": concrete_invalidation_row_count,
                "missing_invalidation_row_count": len(rows)
                - concrete_invalidation_row_count,
                "limitation_count": len(limitations),
            },
        ),
        _check(
            "manual_adoption_boundary",
            "self_review",
            "pass" if boundary_present else "fail",
            "Opinion-facing text was scanned for forbidden execution or advice language.",
            "Forbidden execution or advice wording blocks manual-adoption boundary."
            if not boundary_present
            else "Manual adoption boundary is preserved.",
            _refs(("version_pack", "manual_adoption_only")),
            {"manual_adoption_only": True, "forbidden_language_found": not boundary_present},
        ),
        _check(
            "insufficient_evidence_gate",
            "self_review",
            "pass" if not limitations or state in {"no-opinion", "do-not-adopt"} else "fail",
            "Downgrade matrix was applied to current artifact limitations.",
            "Unavailable evidence must not emit viable action rows.",
            _refs(("artifact_completeness", "artifact_completeness")),
            {"state": state, "limitation_count": len(limitations)},
        ),
        _check(
            "source_artifact_audit",
            "source_provider_audit",
            "warning" if source_audit_result["config_fallback_metadata_present"] else "not_evaluated",
            "Config/fallback metadata is separate from unavailable raw provider/parser audit metadata."
            if source_audit_result["config_fallback_metadata_present"]
            else "No config, fallback, raw provider, or parser audit metadata is available.",
            "Raw provider/parser audit coverage is unavailable in current persisted run artifacts.",
            _refs(("config_sources", "config_sources"), ("fallback_audit", "fallback_audit")),
            source_audit_result,
        ),
        _check(
            "text_evidence_summary",
            "evidence_summary",
            "warning" if text_sources else "not_evaluated",
            "Persisted warning or caveat text was summarized from the same response surface."
            if text_sources
            else "No persisted warning, caveat, or source text exists on this response surface.",
            "No generated advice text is used.",
            text_result["source_artifact_references"] or _refs(("warnings", "warnings")),
            text_result,
        ),
    ]
    boundary_present = _manual_boundary_present(*_opinion_texts(payload, rows, checks))
    for item in checks:
        if item["check"] == "manual_adoption_boundary":
            item["status"] = "pass" if boundary_present else "fail"
            item["risk_or_warning"] = (
                "Forbidden execution or advice wording blocks manual-adoption boundary."
                if not boundary_present
                else "Manual adoption boundary is preserved."
            )
            item["result"] = {
                "manual_adoption_only": True,
                "forbidden_language_found": not boundary_present,
                "scanned_review_check_copy": True,
            }
        elif item["check"] == "backtest_report_discipline":
            item["result"]["research_only_boundary_present"] = boundary_present
            if not boundary_present:
                item["risk_or_warning"] = (
                    "Caveats, missing policy metadata, or boundary wording prevent a clean pass."
                )
            if (
                item["result"]["metric_keys"]
                and item["result"]["threshold_policy_version_present"]
                and item["result"]["price_basis_version_present"]
                and boundary_present
                and item["result"]["caveat_count"] == 0
            ):
                item["status"] = "pass"
            elif item["result"]["metric_keys"]:
                item["status"] = "warning"
            else:
                item["status"] = "fail"
    return checks


def _empty_artifact(
    state: str,
    reason: str,
    limitations: list[str],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_version": OPINION_ARTIFACT_VERSION,
        "state": state,
        "state_reason": reason,
        "manual_adoption_only": True,
        "evidence_limitations": limitations,
        "buy_candidates": [],
        "sell_or_avoid": [],
        "watch": [],
        "review_checks": _review_checks(payload, [], state, limitations),
    }


def build_opinion_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("summary_only"):
        return {
            "artifact_version": OPINION_ARTIFACT_VERSION,
            "state": "no-opinion",
            "state_reason": OMITTED_DETAIL_LIMITATION,
            "manual_adoption_only": True,
            "evidence_limitations": [OMITTED_DETAIL_LIMITATION],
            "buy_candidates": [],
            "sell_or_avoid": [],
            "watch": [],
            "review_checks": _summary_checks(),
        }

    limitations: list[str] = []
    status = payload.get("status")
    completeness = payload.get("artifact_completeness")
    if status is not None and status != "succeeded":
        limitations.append(f"Run status is {status}; artifacts are not adoptable.")
    if completeness != "complete":
        missing = [str(item) for item in _as_list(payload.get("missing_artifacts"))]
        detail = f" Missing artifacts: {', '.join(missing)}." if missing else ""
        limitations.append(f"Artifact completeness is {completeness}.{detail}")
    if not _as_mapping(payload.get("metrics")):
        limitations.append("Strategy metrics artifact is unavailable.")
    if not _as_mapping(payload.get("model_diagnostics")):
        limitations.append("Model diagnostics artifact is unavailable.")
    if not _as_list(payload.get("signals")):
        limitations.append("Signal artifact is unavailable.")
    if payload.get("stale_mark_days_with_open_positions") or payload.get("stale_risk_share"):
        limitations.append("Stale mark risk is present in persisted artifacts.")

    if status is not None and status != "succeeded":
        return _empty_artifact(
            "do-not-adopt",
            "Research run did not complete successfully.",
            limitations,
            payload,
        )
    if limitations:
        return _empty_artifact(
            "no-opinion",
            "Persisted artifacts are insufficient for a traceable opinion.",
            limitations,
            payload,
        )

    rows = _action_rows(payload)
    if not rows:
        limitations = ["Signal rows lacked symbol, score, or position fields."]
        return _empty_artifact(
            "no-opinion",
            "No valid symbol-level signal rows were available.",
            limitations,
            payload,
        )

    buy_candidates = [row for row in rows if row["position_signal"] > 0]
    sell_or_avoid = [row for row in rows if row["position_signal"] < 0]
    watch = [row for row in rows if row["position_signal"] == 0]
    artifact = {
        "artifact_version": OPINION_ARTIFACT_VERSION,
        "state": "viable",
        "state_reason": "Complete persisted research artifacts support traceable opinion rows.",
        "manual_adoption_only": True,
        "evidence_limitations": [],
        "buy_candidates": buy_candidates,
        "sell_or_avoid": sell_or_avoid,
        "watch": watch,
    }
    initial_checks = _review_checks(
        {**payload, "state_reason": artifact["state_reason"]},
        rows,
        "viable",
        [],
    )
    artifact["review_checks"] = initial_checks
    failed_checks = {
        item["check"]: item for item in initial_checks if item["status"] == "fail"
    }
    if failed_checks:
        artifact["state"] = "no-opinion"
        artifact["state_reason"] = "Self-review gates blocked a viable opinion."
        artifact["evidence_limitations"] = [
            "One or more self-review gates failed; reload details before adopting."
        ]
        artifact["buy_candidates"] = []
        artifact["sell_or_avoid"] = []
        artifact["watch"] = []
        final_checks = _review_checks(
            {**payload, "state_reason": artifact["state_reason"]},
            rows,
            artifact["state"],
            artifact["evidence_limitations"],
        )
        for item in final_checks:
            if item["check"] in failed_checks:
                item.update(failed_checks[item["check"]])
        artifact["review_checks"] = final_checks
    return artifact
