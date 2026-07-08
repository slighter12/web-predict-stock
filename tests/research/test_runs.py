from types import SimpleNamespace
from copy import deepcopy

import pytest

import backend.research.domain.opinion as opinion_domain
import backend.research.services.runs as research_run_service
from backend.platform.errors import DataAccessError
from backend.research.contracts.runs import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
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
        strategy={
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 3,
            "allow_proactive_sells": True,
        },
        execution={"slippage": 0.001, "fees": 0.002},
        baselines=[],
    )


def make_response(run_id: str = "run_123") -> ResearchRunResponse:
    return ResearchRunResponse(
        run_id=run_id,
        metrics=Metrics(
            total_return=0.12, sharpe=1.1, max_drawdown=-0.08, turnover=0.3
        ),
        equity_curve=[{"date": "2024-01-02", "equity": 1.0}],
        signals=[
            {"date": "2024-01-02", "symbol": "2330", "score": 0.01, "position": 1.0}
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


def make_opinion_payload() -> dict:
    return {
        "status": "succeeded",
        "request_payload": {
            "symbols": ["2330"],
            "strategy": {"threshold": 0.003, "top_n": 2},
        },
        "effective_strategy": {"threshold": 0.003, "top_n": 2},
        "metrics": {"total_return": 0.12, "sharpe": 1.1},
        "model_diagnostics": {"task": "regression", "sample_count": 2},
        "signals": [
            {"date": "2024-01-02", "symbol": "2330", "score": 0.01, "position": 1.0},
            {"date": "2024-01-02", "symbol": "2317", "score": -0.02, "position": -1.0},
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


def test_opinion_builder_uses_latest_dated_signal_rows_for_actions_and_checks():
    payload = make_opinion_payload()
    payload["signals"] = [
        {"date": "2024-01-03", "symbol": "2330", "score": 0.02, "position": 1.0},
        {"date": "2024-01-01", "symbol": "2330", "score": -0.04, "position": -1.0},
        {"date": "2024-01-01", "symbol": "2317", "score": 0.04, "position": 1.0},
        {"date": "2024-01-04", "symbol": "2317", "score": -0.03, "position": -1.0},
        {"date": "2024-01-04", "symbol": "2454", "score": 0.0, "position": 0.0},
        {"date": "2024-01-04", "symbol": "9999", "score": None, "position": 1.0},
        {"date": "not-a-date", "symbol": "8888", "score": 0.5, "position": 1.0},
    ]

    artifact = build_opinion_artifact(payload)
    checks = {item["check"]: item for item in artifact["review_checks"]}

    assert [row["symbol"] for row in artifact["buy_candidates"]] == ["2330"]
    assert [row["symbol"] for row in artifact["sell_or_avoid"]] == ["2317"]
    assert [row["symbol"] for row in artifact["watch"]] == ["2454"]
    assert all(row["symbol"] != "8888" for row in artifact["buy_candidates"])
    assert {
        ref["date"]
        for ref in artifact["buy_candidates"][0]["source_artifact_references"]
        if ref["artifact"] == "signals" and "date" in ref
    } == {"2024-01-03"}
    assert checks["signal_to_position"]["result"] == {
        "checked_symbol_count": 5,
        "positive_count": 1,
        "negative_count": 1,
        "flat_count": 1,
        "invalid_row_count": 2,
    }
    assert checks["parameter_sensitivity"]["result"]["base_candidate_symbols"] == [
        "2330"
    ]
    assert checks["parameter_sensitivity"]["result"]["scenario_candidate_counts"][
        "top_n_minus_1"
    ] == 1


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
        "send through order routing",
        "automatic rebalance from this opinion",
        "automatic rebalancing from this opinion",
        "broker action from this signal",
        "account control instruction",
        "personalized investment advice",
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


def test_opinion_builder_stale_evidence_blocks_forced_rows():
    payload = make_opinion_payload()
    payload["stale_risk_share"] = 0.25

    artifact = build_opinion_artifact(payload)

    assert artifact["state"] == "no-opinion"
    assert artifact["buy_candidates"] == []
    assert "Stale mark risk" in " ".join(artifact["evidence_limitations"])


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
