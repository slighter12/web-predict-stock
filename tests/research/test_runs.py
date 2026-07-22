from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import backend.research.domain.opinion as opinion_domain
import backend.research.services.runs as research_run_service
from backend.platform.errors import DataAccessError
from backend.research.contracts.runs import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
    OpinionReviewCheck,
    OpinionRow,
    ResearchRunCreateRequest,
    ResearchRunResponse,
)
from backend.research.domain.opinion import build_opinion_artifact
from backend.research.domain.version_pack import build_version_pack_payload


def make_request() -> ResearchRunCreateRequest:
    return ResearchRunCreateRequest(
        runtime_mode="runtime_compatibility_mode",
        market="TW",
        symbols=["2330"],
        date_range={"start": "2022-01-01", "end": "2024-01-01"},
        return_target="open_to_open",
        horizon_days=1,
        features=[{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        model={"type": "xgboost", "params": {}},
        direction_model={"type": "extra_trees", "params": {}},
        strategy={
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 3,
            "allow_proactive_sells": True,
        },
        execution={"slippage": 0.001, "fees": 0.002},
        baselines=[],
    )


def test_new_research_request_rejects_unshifted_features():
    payload = make_request().model_dump(mode="json")
    payload["features"][0]["shift"] = 0

    with pytest.raises(ValidationError):
        ResearchRunCreateRequest.model_validate(payload)


def make_response(run_id: str = "run_123") -> ResearchRunResponse:
    return ResearchRunResponse(
        run_id=run_id,
        metrics=Metrics(
            total_return=0.12, sharpe=1.1, max_drawdown=-0.08, turnover=0.3
        ),
        equity_curve=[{"date": "2024-01-02", "equity": 1.0}],
        signals=[
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "score": 0.01,
                "position": 1.0,
                "signal_kind": "forward_opinion",
                "up_probability": 0.8,
                "predicted_direction": "up",
            }
        ],
        validation=None,
        model_diagnostics={
            "task": "regression",
            "sample_count": 2,
            "rmse": 0.1,
            "mae": 0.08,
            "rank_ic": 0.2,
            "linear_ic": 0.1,
            "actual_vs_predicted": [],
            "residuals": [],
            "feature_importance": [],
            "direction_classification": {
                "evaluation_status": "evaluated",
                "sample_count": 2,
            },
        },
        baselines={},
        warnings=[],
        runtime_mode="runtime_compatibility_mode",
        default_bundle_version=None,
        effective_strategy=EffectiveStrategyConfig(threshold=0.003, top_n=3),
        config_sources=ConfigSources.model_validate(
            {"strategy": {"threshold": "request_override", "top_n": "request_override"}}
        ),
        fallback_audit=FallbackAudit.model_validate(
            {
                "strategy": {
                    "threshold": {"attempted": False, "outcome": "not_needed"},
                    "top_n": {"attempted": False, "outcome": "not_needed"},
                }
            }
        ),
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "research_only_comparable",
                "scoring_factor_ids": [],
            }
        ),
    )


def test_requested_missing_baseline_marks_response_partial():
    request = make_request()
    request.baselines = ["buy_and_hold", "naive_momentum"]
    response = make_response("run_missing_baseline").model_copy(
        update={"baselines": {"buy_and_hold": {"sharpe": 0.5}}}
    )

    response = research_run_service._response_with_artifact_summary(
        response, request
    )

    assert response.artifact_completeness == "partial"
    assert "baselines" in response.missing_artifacts
    assert "baselines" not in response.present_artifacts


def make_opinion_payload() -> dict:
    return {
        "status": "succeeded",
        "request_payload": {
            "symbols": ["2330", "2317"],
            "strategy": {"threshold": 0.003, "top_n": 2},
            "direction_model": {"confirmation_probability_threshold": 0.5},
        },
        "effective_strategy": {"threshold": 0.003, "top_n": 2},
        "metrics": {"total_return": 0.12, "sharpe": 1.1},
        "model_diagnostics": {
            "task": "regression",
            "sample_count": 2,
            "rmse": 0.1,
            "direction_classification": {"evaluation_status": "evaluated"},
        },
        "signals": [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "score": 0.01,
                "position": 1.0,
                "signal_kind": "forward_opinion",
                "up_probability": 0.8,
                "predicted_direction": "up",
            },
            {
                "date": "2024-01-02",
                "symbol": "2317",
                "score": -0.02,
                "position": 0.0,
                "signal_kind": "forward_opinion",
                "up_probability": 0.2,
                "predicted_direction": "down",
            },
        ],
        "validation": {"method": "walk_forward", "metrics": {"rmse": 0.1}},
        "baselines": {"buy_hold": {"total_return": 0.05}},
        "warnings": [],
        "config_sources": {"strategy": {"threshold": "request_override"}},
        "fallback_audit": {"strategy": {"threshold": {"attempted": False}}},
        "artifact_completeness": "complete",
        "missing_artifacts": [],
        "comparison_caveats": [],
        "threshold_policy_version": "static_absolute_gross_label_v1",
        "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
    }


def test_opinion_contract_requires_source_artifact_references():
    row_payload = {
        "symbol": "2330",
        "model_score": 0.01,
        "position_signal": 1.0,
        "signal_date": "2024-01-02",
        "up_probability": 0.8,
        "confirmation_state": "confirmed",
        "evidence_reason": "Latest persisted signal was checked.",
        "risk_or_warning": "Persisted warning was checked.",
        "invalidation_note": "Newer persisted data may supersede this signal.",
    }
    check_payload = {
        "check": "risk_present",
        "category": "self_review",
        "status": "pass",
        "evidence_reason": "Risk context was checked.",
        "risk_or_warning": "Persisted warning was checked.",
        "result": {"risk_checked": True},
    }

    with pytest.raises(ValidationError):
        OpinionRow.model_validate(row_payload)
    with pytest.raises(ValidationError):
        OpinionRow.model_validate({**row_payload, "source_artifact_references": []})
    with pytest.raises(ValidationError):
        OpinionReviewCheck.model_validate(check_payload)
    with pytest.raises(ValidationError):
        OpinionReviewCheck.model_validate(
            {**check_payload, "source_artifact_references": []}
        )


def test_opinion_contract_rejects_unknown_check_and_category():
    payload = {
        "check": "risk_present",
        "category": "self_review",
        "status": "pass",
        "evidence_reason": "Risk context was checked.",
        "risk_or_warning": "Persisted warning was checked.",
        "source_artifact_references": [
            {"artifact": "warnings", "field": "warnings"}
        ],
        "result": {"risk_checked": True},
    }

    with pytest.raises(ValidationError):
        OpinionReviewCheck.model_validate({**payload, "check": "unknown"})
    with pytest.raises(ValidationError):
        OpinionReviewCheck.model_validate({**payload, "category": "unknown"})


@pytest.mark.parametrize("status", ["pass", "warning", "fail"])
def test_opinion_contract_requires_result_for_evaluated_checks(status):
    payload = {
        "check": "risk_present",
        "category": "self_review",
        "status": status,
        "evidence_reason": "Risk context was checked.",
        "risk_or_warning": "Persisted warning was checked.",
        "source_artifact_references": [
            {"artifact": "warnings", "field": "warnings"}
        ],
        "result": {},
    }

    with pytest.raises(
        ValidationError,
        match="evaluated review checks require a non-empty result",
    ):
        OpinionReviewCheck.model_validate(payload)


def test_opinion_contract_allows_default_result_for_not_evaluated_check():
    check = OpinionReviewCheck.model_validate(
        {
            "check": "risk_present",
            "category": "self_review",
            "status": "not_evaluated",
            "evidence_reason": "Persisted warnings are unavailable.",
            "risk_or_warning": "Risk could not be evaluated.",
            "source_artifact_references": [
                {"artifact": "warnings", "field": "warnings"}
            ],
        }
    )

    assert check.result == {}


def test_opinion_builder_uses_latest_dated_signal_rows_for_actions_and_checks():
    payload = make_opinion_payload()
    payload["symbols"] = ["2330", "2317", "2454", "9999", "8888"]
    payload["signals"] = [
        {
            "date": datetime(2024, 1, 4, 12, 30),
            "symbol": "2330",
            "score": 0.02,
            "position": 1.0,
        },
        {"date": "2024-01-01", "symbol": "2330", "score": -0.04, "position": -1.0},
        {"date": "2024-01-01", "symbol": "2317", "score": 0.04, "position": 1.0},
        {"date": "2024-01-04", "symbol": "2317", "score": -0.03, "position": -1.0},
        {"date": "2024-01-04", "symbol": "2454", "score": 0.0, "position": 0.0},
        {"date": "2024-01-04", "symbol": "9999", "score": None, "position": 1.0},
        {"date": "not-a-date", "symbol": "8888", "score": 0.5, "position": 1.0},
        {"date": "2024-01-04", "score": 0.5, "position": 1.0},
    ]

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert checks["signal_to_position"]["status"] == "fail"
    assert "holdout evaluation signals are not investment opinions" in " ".join(
        artifact["evidence_limitations"]
    )


def test_opinion_builder_undeclared_signal_symbol_blocks_viability():
    payload = make_opinion_payload()
    payload["signals"].append(
        {
            "date": "2024-01-02",
            "symbol": "2454",
            "score": 0.03,
            "position": 1.0,
            "signal_kind": "forward_opinion",
            "up_probability": 0.8,
            "predicted_direction": "up",
        }
    )

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert "outside the declared run universe: 2454" in " ".join(
        artifact["evidence_limitations"]
    )


@pytest.mark.parametrize(
    "up_probability",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
)
def test_opinion_builder_rejects_invalid_persisted_up_probability(up_probability):
    payload = make_opinion_payload()
    payload["signals"][0]["up_probability"] = up_probability

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert "exactly one valid row" in " ".join(artifact["evidence_limitations"])


def test_opinion_builder_parameter_sensitivity_reports_partial_scenario_change():
    payload = make_opinion_payload()
    payload["signals"] = [
        {
            "date": "2024-01-02", "symbol": "2330", "score": 0.004,
            "position": 1.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
        {
            "date": "2024-01-02", "symbol": "2317", "score": 0.003,
            "position": 1.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
    ]

    checks = {
        item["check"]: item for item in build_opinion_artifact(payload)["review_checks"]
    }

    result = checks["parameter_sensitivity"]["result"]
    assert result["scenario_candidate_counts"] == {
        "strict_threshold": 1,
        "loose_threshold": 2,
        "top_n_minus_1": 1,
        "top_n_plus_1": 2,
    }
    assert result["changed_symbols"] == ["2317"]


def test_opinion_builder_uses_hybrid_action_rules():
    payload = make_opinion_payload()
    payload["request_payload"]["symbols"] = ["BUY", "CONFLICT", "SELL", "RANKED_OUT"]
    payload["signals"] = [
        {
            "date": "2024-01-02", "symbol": "BUY", "score": 0.02,
            "position": 1.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
        {
            "date": "2024-01-02", "symbol": "CONFLICT", "score": 0.02,
            "position": 0.0, "signal_kind": "forward_opinion",
            "up_probability": 0.2, "predicted_direction": "down",
        },
        {
            "date": "2024-01-02", "symbol": "SELL", "score": -0.01,
            "position": 0.0, "signal_kind": "forward_opinion",
            "up_probability": 0.2, "predicted_direction": "down",
        },
        {
            "date": "2024-01-02", "symbol": "RANKED_OUT", "score": 0.01,
            "position": 0.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
    ]

    artifact = build_opinion_artifact(payload)

    assert [row["symbol"] for row in artifact["buy_candidates"]] == ["BUY"]
    assert [row["symbol"] for row in artifact["sell_or_avoid"]] == ["SELL"]
    assert [row["symbol"] for row in artifact["watch"]] == [
        "CONFLICT",
        "RANKED_OUT",
    ]


def test_opinion_builder_keeps_each_symbol_latest_parseable_signal():
    payload = make_opinion_payload()
    payload["signals"] = [
        {
            "date": "2024-01-01", "symbol": "2330", "score": 0.01,
            "position": 1.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
        {
            "date": "2024-01-02", "symbol": "2317", "score": 0.02,
            "position": 1.0, "signal_kind": "forward_opinion",
            "up_probability": 0.8, "predicted_direction": "up",
        },
    ]

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert checks["signal_to_position"]["status"] == "warning"


def test_opinion_builder_robustness_does_not_pass_empty_validation_metrics():
    payload = make_opinion_payload()
    payload["validation"] = {"method": "walk_forward", "metrics": {}}
    payload["baselines"] = {}
    payload["comparison_caveats"] = [
        {"code": "REVIEW_ARTIFACTS_MISSING", "label": "missing", "severity": "blocker"}
    ]

    checks = {
        item["check"]: item for item in build_opinion_artifact(payload)["review_checks"]
    }

    assert checks["robustness"]["status"] == "warning"
    assert checks["robustness"]["result"] == {
        "validation_metric_keys": [],
        "baseline_keys": [],
        "warning_count": 0,
        "blocker_caveat_count": 1,
    }


def _valid_opinion_row() -> dict:
    return deepcopy(
        build_opinion_artifact(make_opinion_payload())["buy_candidates"][0]
    )


def _assert_self_review_blocks_viability(artifact: dict, check_name: str) -> None:
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert checks[check_name]["status"] == "fail"
    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert artifact["sell_or_avoid"] == []
    assert artifact["watch"] == []
    assert artifact["evidence_limitations"]
    assert checks["insufficient_evidence_gate"]["status"] == "pass"
    assert checks["insufficient_evidence_gate"]["result"] == {
        "state": "no-opinion",
        "limitation_count": len(artifact["evidence_limitations"]),
    }


def test_opinion_builder_missing_row_specific_signal_ref_blocks_viability(
    monkeypatch,
):
    row = _valid_opinion_row()
    for reference in row["source_artifact_references"]:
        if reference["artifact"] == "signals":
            reference.pop("symbol", None)
            reference.pop("date", None)
    monkeypatch.setattr(opinion_domain, "_action_rows", lambda payload: [row])

    artifact = build_opinion_artifact(make_opinion_payload())

    _assert_self_review_blocks_viability(artifact, "evidence_traceability")


def test_opinion_builder_wrong_signal_ref_date_blocks_viability(monkeypatch):
    row = _valid_opinion_row()
    for reference in row["source_artifact_references"]:
        if reference["artifact"] == "signals":
            reference["date"] = "2024-01-01"
    monkeypatch.setattr(opinion_domain, "_action_rows", lambda payload: [row])

    artifact = build_opinion_artifact(make_opinion_payload())

    _assert_self_review_blocks_viability(artifact, "evidence_traceability")


def test_opinion_builder_nonexistent_invalidation_signal_field_blocks_viability(
    monkeypatch,
):
    row = _valid_opinion_row()
    for reference in row["source_artifact_references"]:
        if reference["artifact"] == "signals":
            reference["field"] = "missing"
    monkeypatch.setattr(opinion_domain, "_action_rows", lambda payload: [row])

    artifact = build_opinion_artifact(make_opinion_payload())

    _assert_self_review_blocks_viability(artifact, "invalidation_present")


def test_opinion_builder_generic_risk_disclaimer_blocks_viability(monkeypatch):
    row = _valid_opinion_row()
    row["risk_or_warning"] = "Research-only opinion for manual review."
    monkeypatch.setattr(opinion_domain, "_action_rows", lambda payload: [row])

    artifact = build_opinion_artifact(make_opinion_payload())

    _assert_self_review_blocks_viability(artifact, "risk_present")


def test_opinion_builder_static_invalidation_template_blocks_viability(monkeypatch):
    row = _valid_opinion_row()
    row["invalidation_note"] = "Do not adopt this signal."
    monkeypatch.setattr(opinion_domain, "_action_rows", lambda payload: [row])

    artifact = build_opinion_artifact(make_opinion_payload())

    _assert_self_review_blocks_viability(artifact, "invalidation_present")


@pytest.mark.parametrize(
    "forbidden_text",
    [
        "execution-ready signal",
        "live_order readiness",
        "send through order routing",
        "automatic rebalance from this opinion",
        "automatic rebalancing from this opinion",
        "broker-routing action from this signal",
        "portfolio-control instruction",
        "account control instruction",
        "personalized investment advice",
        "Execution route research_only produced 1 order record(s).",
    ],
)
def test_opinion_builder_manual_boundary_variants_downgrade_viability(
    forbidden_text,
):
    payload = make_opinion_payload()
    payload["warnings"] = [forbidden_text]

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert checks["manual_adoption_boundary"]["status"] == "fail"
    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert artifact["evidence_limitations"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_route", "broker-routing-v1"),
        ("tradability_state", "execution_ready"),
        ("live_control_profile_id", "broker-routing-profile"),
        ("live_control_version", "live_order_controls_v1"),
    ],
)
def test_opinion_builder_manual_boundary_scans_execution_metadata(field, value):
    payload = make_opinion_payload()
    payload[field] = value

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert checks["manual_adoption_boundary"]["status"] == "fail"
    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []


def test_opinion_builder_manual_boundary_allows_broker_metadata_description():
    payload = make_opinion_payload()
    payload["warnings"] = ["Broker comparison metadata is unavailable."]

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert checks["manual_adoption_boundary"]["status"] == "pass"


def test_opinion_builder_manual_boundary_allows_research_only_tradability():
    payload = make_opinion_payload()
    payload["tradability_state"] = "research_only"

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "viable"


def test_opinion_builder_manual_boundary_scans_review_check_copy(monkeypatch):
    def fake_parameter_sensitivity(payload):
        return {
            "status": "warning",
            "reason": "Local provisional sensitivity scenarios were computed.",
            "result": {
                "base_candidate_symbols": ["2330"],
                "scenario_candidate_counts": {},
                "stable_symbols": [],
                "changed_symbols": [],
                "provisional_policy": "execution-ready review output",
                "skipped_scenarios": [],
            },
        }

    monkeypatch.setattr(
        opinion_domain,
        "_parameter_sensitivity",
        fake_parameter_sensitivity,
    )

    artifact = build_opinion_artifact(make_opinion_payload())
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert checks["manual_adoption_boundary"]["status"] == "fail"
    assert checks["manual_adoption_boundary"]["result"]["scanned_review_check_copy"]
    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert artifact["evidence_limitations"]


def test_opinion_builder_source_audit_names_missing_config_inputs():
    payload = make_opinion_payload()
    payload["config_sources"] = None
    payload["fallback_audit"] = None

    checks = {
        item["check"]: item for item in build_opinion_artifact(payload)["review_checks"]
    }

    assert checks["source_artifact_audit"]["status"] == "not_evaluated"
    assert checks["source_artifact_audit"]["result"]["config_sources_present"] is False
    assert checks["source_artifact_audit"]["result"]["fallback_audit_present"] is False
    assert checks["source_artifact_audit"]["result"][
        "missing_config_fallback_inputs"
    ] == ["config_sources", "fallback_audit"]


@pytest.mark.parametrize(
    ("metrics", "diagnostics"),
    [
        (
            {
                "total_return": None,
                "sharpe": None,
                "max_drawdown": None,
                "turnover": None,
                "max_position_weight": None,
            },
            {"task": "regression", "sample_count": 2, "rmse": 0.1},
        ),
        (
            {"total_return": 0.0},
            {
                "task": "regression",
                "sample_count": 0,
                "rmse": 0.1,
                "mae": None,
                "rank_ic": None,
                "linear_ic": None,
            },
        ),
        (
            {"total_return": float("nan")},
            {"task": "regression", "sample_count": 2, "rmse": 0.1},
        ),
        (
            {"total_return": float("inf")},
            {"task": "regression", "sample_count": 2, "rmse": 0.1},
        ),
        (
            {"total_return": float("-inf")},
            {"task": "regression", "sample_count": 2, "rmse": 0.1},
        ),
        (
            {"total_return": 0.0},
            {"task": "regression", "sample_count": 2, "rmse": float("nan")},
        ),
        (
            {"total_return": 0.0},
            {"task": "regression", "sample_count": 2, "rmse": float("inf")},
        ),
        (
            {"total_return": 0.0},
            {"task": "regression", "sample_count": 2, "rmse": float("-inf")},
        ),
    ],
)
def test_opinion_builder_requires_numeric_metrics_and_diagnostics(
    metrics,
    diagnostics,
):
    payload = make_opinion_payload()
    payload["metrics"] = metrics
    payload["model_diagnostics"] = diagnostics

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []


def test_opinion_builder_unscoped_warning_blocks_all_rows():
    payload = make_opinion_payload()
    payload["signals"] = [payload["signals"][0]]
    payload["warnings"] = ["Data source degraded."]

    artifact = build_opinion_artifact(payload)
    check = next(
        item for item in artifact["review_checks"] if item["check"] == "risk_present"
    )

    assert artifact["state"] == "no-opinion"
    assert check["result"]["concrete_risk_row_count"] == 0
    assert "run-level/unscoped" in check["risk_or_warning"]


def test_opinion_builder_symbol_scoped_warning_does_not_cover_other_rows():
    payload = make_opinion_payload()
    payload["warnings"] = ["Data source degraded for 2330."]

    artifact = build_opinion_artifact(payload)
    check = next(
        item for item in artifact["review_checks"] if item["check"] == "risk_present"
    )

    assert artifact["state"] == "no-opinion"
    assert check["result"]["concrete_risk_row_count"] == 1
    assert check["result"]["missing_risk_row_count"] == 1


def test_opinion_builder_matches_each_row_against_all_symbol_warnings():
    payload = make_opinion_payload()
    payload["warnings"] = [
        "Data source degraded for 2317.",
        "Data source degraded for 2330.",
    ]

    artifact = build_opinion_artifact(payload)
    check = next(
        item for item in artifact["review_checks"] if item["check"] == "risk_present"
    )

    assert artifact["state"] == "viable"
    assert "reviewable, traceable model output" in artifact["state_reason"]
    assert "do not establish out-of-sample skill or investment viability" in artifact[
        "state_reason"
    ]
    assert check["result"]["concrete_risk_row_count"] == 2
    assert check["result"]["missing_risk_row_count"] == 0


def test_opinion_builder_stale_evidence_blocks_forced_rows():
    payload = make_opinion_payload()
    payload["stale_risk_share"] = 0.25

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert "Stale mark risk" in " ".join(artifact["evidence_limitations"])


def test_opinion_builder_missing_status_is_do_not_adopt():
    payload = make_opinion_payload()
    payload.pop("status")

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "do-not-adopt"
    assert artifact["buy_candidates"] == []
    assert "Run status is unavailable" in " ".join(artifact["evidence_limitations"])


def test_create_response_stale_evidence_blocks_opinion_rows():
    response = make_response().model_copy(update={"stale_risk_share": 0.25})

    result = research_run_service._response_with_artifact_summary(
        response,
        make_request(),
    )

    assert result.opinion_artifact.state == "no-opinion"
    assert result.opinion_artifact.buy_candidates == []


def test_create_response_execution_metadata_blocks_opinion_rows():
    response = make_response().model_copy(
        update={"tradability_state": "execution_ready"}
    )

    result = research_run_service._response_with_artifact_summary(
        response,
        make_request(),
    )
    checks = {item.check: item for item in result.opinion_artifact.review_checks}

    assert checks["manual_adoption_boundary"].status == "fail"
    assert result.opinion_artifact.state == "no-opinion"
    assert result.opinion_artifact.buy_candidates == []


def test_opinion_builder_text_evidence_summary_does_not_invent_prose():
    payload = make_opinion_payload()

    checks = {
        item["check"]: item for item in build_opinion_artifact(deepcopy(payload))["review_checks"]
    }

    assert checks["text_evidence_summary"]["status"] == "not_evaluated"
    assert checks["text_evidence_summary"]["result"]["source_text_count"] == 0
    assert checks["text_evidence_summary"]["result"]["summary_text"] == ""


def test_create_research_run_fails_when_success_registry_write_fails(monkeypatch):
    started_calls: list[str] = []

    monkeypatch.setattr(
        research_run_service,
        "execute_research_run",
        lambda **kwargs: SimpleNamespace(
            runtime_context={
                "strategy": {
                    "threshold": 0.003,
                    "top_n": 3,
                    "allow_proactive_sells": True,
                }
            },
            response=make_response("run_strict"),
            validation_summary=None,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        research_run_service,
        "record_started",
        lambda **kwargs: started_calls.append(kwargs["run_id"]) or kwargs,
    )
    monkeypatch.setattr(
        research_run_service,
        "record_success",
        lambda **kwargs: (_ for _ in ()).throw(DataAccessError("db unavailable")),
    )

    with pytest.raises(DataAccessError, match="db unavailable"):
        research_run_service.create_research_run(
            request=make_request(),
            request_id="req_123",
            run_id="run_strict",
        )
    assert started_calls == ["run_strict"]


def test_create_research_run_records_started_before_execute(monkeypatch):
    call_order: list[str] = []

    monkeypatch.setattr(
        research_run_service,
        "record_started",
        lambda **kwargs: call_order.append("started") or kwargs,
    )

    def fake_execute_research_run(**kwargs):
        assert call_order == ["started"]
        call_order.append("executed")
        return SimpleNamespace(
            runtime_context={
                "strategy": {
                    "threshold": 0.003,
                    "top_n": 3,
                    "allow_proactive_sells": True,
                }
            },
            response=make_response(kwargs["run_id"]),
            validation_summary=None,
            warnings=[],
        )

    monkeypatch.setattr(
        research_run_service,
        "execute_research_run",
        fake_execute_research_run,
    )
    monkeypatch.setattr(
        research_run_service,
        "record_success",
        lambda **kwargs: call_order.append("success") or kwargs,
    )

    response = research_run_service.create_research_run(
        request=make_request(),
        request_id="req_123",
        run_id="run_started",
    )

    assert response.run_id == "run_started"
    assert response.artifact_completeness == "complete"
    assert response.not_required_artifacts == ["validation", "baselines"]
    assert response.opinion_artifact.state == "viable"
    assert response.opinion_artifact.sell_or_avoid == []
    assert response.opinion_artifact.watch == []
    opinion_row = response.opinion_artifact.buy_candidates[0]
    assert opinion_row.symbol == "2330"
    assert opinion_row.model_score == pytest.approx(0.01)
    assert opinion_row.position_signal == pytest.approx(1.0)
    assert opinion_row.evidence_reason
    assert opinion_row.risk_or_warning
    assert opinion_row.invalidation_note
    assert {item.artifact for item in opinion_row.source_artifact_references} >= {
        "signals",
        "model_diagnostics",
        "metrics",
        "artifact_completeness",
    }
    checks = {item.check: item for item in response.opinion_artifact.review_checks}
    assert {
        "strategy_lifecycle",
        "signal_to_position",
        "backtest_report_discipline",
        "robustness",
        "parameter_sensitivity",
        "evidence_traceability",
        "risk_present",
        "invalidation_present",
        "manual_adoption_boundary",
        "insufficient_evidence_gate",
        "source_artifact_audit",
        "text_evidence_summary",
    } <= set(checks)
    assert checks["strategy_lifecycle"].status == "pass"
    assert checks["signal_to_position"].status == "pass"
    assert checks["backtest_report_discipline"].status == "pass"
    assert checks["manual_adoption_boundary"].status == "pass"
    assert checks["strategy_lifecycle"].result["metrics_present"]
    assert checks["signal_to_position"].result["checked_symbol_count"] == 1
    assert checks["robustness"].status == "warning"
    assert checks["parameter_sensitivity"].status == "pass"
    assert checks["parameter_sensitivity"].result["base_candidate_symbols"] == [
        "2330"
    ]
    assert checks["source_artifact_audit"].status == "warning"
    assert checks["text_evidence_summary"].status == "not_evaluated"
    assert call_order == ["started", "executed", "success"]
