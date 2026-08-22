from datetime import date

import pytest

import backend.research.services.registry as registry_service
from backend.research.domain.version_pack import build_version_pack_payload
from backend.research.domain.result_caveats import (
    TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
    warnings_with_result_caveats,
)
from backend.platform.errors import UnsupportedConfigurationError
from backend.research.contracts.runs import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
    ResearchRunCreateRequest,
    ResearchRunResponse,
)
from backend.shared.analytics.features import FEATURE_REGISTRY_VERSION


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
        equity_curve=[{"date": date(2024, 1, 2), "equity": 1.0}],
        signals=[
            {"date": date(2024, 1, 2), "symbol": "2330", "score": 0.01, "position": 1.0}
        ],
        validation=None,
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
                "comparison_eligibility": "comparison_metadata_only",
                "scoring_factor_ids": [],
            }
        ),
    )


def test_record_success_builds_registry_payload(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_success(
        run_id="run_123",
        request_id="req_123",
        request=make_request(),
        runtime_context={
            "strategy": {
                "threshold": 0.003,
                "top_n": 3,
                "allow_proactive_sells": True,
            },
            "default_bundle_version": None,
            "config_sources": {
                "strategy": {
                    "threshold": "request_override",
                    "top_n": "request_override",
                }
            },
            "fallback_audit": {
                "strategy": {
                    "threshold": {"attempted": False, "outcome": "not_needed"},
                    "top_n": {"attempted": False, "outcome": "not_needed"},
                }
            },
        },
        response=make_response(),
        validation_summary=None,
        warnings=["warn"],
    )

    assert captured["status"] == "succeeded"
    assert captured["feature_registry_version"] == FEATURE_REGISTRY_VERSION
    assert "feature_registry_version" not in captured["request_payload"]
    assert captured["strategy_type"] == "research_v1"
    assert captured["symbols"] == ["2330"]
    assert captured["metrics"]["total_return"] == pytest.approx(0.12)
    assert captured["warnings"] == [
        "warn",
        TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
    ]
    assert captured["tradability_contract_version"] is None


def test_tw_result_warning_is_deduplicated_and_success_scoped():
    assert warnings_with_result_caveats(
        [
            TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
            TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
        ],
        status="succeeded",
        market="TW",
        request_payload=None,
    ) == [TW_POINT_IN_TIME_MEMBERSHIP_WARNING]
    assert warnings_with_result_caveats(
        [],
        status="running",
        market="TW",
        request_payload=None,
    ) == []
    assert warnings_with_result_caveats(
        [],
        status="succeeded",
        market="US",
        request_payload=None,
    ) == []


def test_record_started_builds_running_payload(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_started(
        run_id="run_123",
        request_id="req_123",
        request=make_request(),
    )

    assert captured["status"] == "running"
    assert captured["strategy_type"] == "research_v1"
    assert captured["symbols"] == ["2330"]
    assert captured["comparison_eligibility"] == "comparison_metadata_only"
    assert captured["feature_registry_version"] == FEATURE_REGISTRY_VERSION
    assert "feature_registry_version" not in captured["request_payload"]


def test_record_rejection_builds_error_code(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_rejection(
        run_id="run_123",
        request_id="req_123",
        request=make_request(),
        runtime_context=None,
        exc=UnsupportedConfigurationError("bad config"),
    )

    assert captured["status"] == "rejected"
    assert captured["validation_outcome"] == {"error_code": "UNSUPPORTED_CONFIGURATION"}
    assert captured["rejection_reason"] == "bad config"


def test_record_failure_builds_data_access_error(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_failure(
        run_id="run_123",
        request_id="req_123",
        request=make_request(),
        runtime_context=None,
        exc=RuntimeError("db unavailable"),
    )

    assert captured["status"] == "failed"
    assert captured["validation_outcome"] == {"error_code": "DATA_ACCESS_FAILED"}


def test_record_validation_failure_uses_raw_request_payload(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_validation_failure(
        run_id="run_123",
        request_id="req_123",
        request_payload={
            "market": "TW",
            "symbols": ["2330"],
            "strategy": {"type": "research_v1", "allow_proactive_sells": True},
        },
        details={
            "fields": [{"field": "symbols", "code": "invalid", "reason": "duplicate"}]
        },
    )

    assert captured["status"] == "validation_failed"
    assert captured["strategy_type"] == "research_v1"
    # A raw legacy payload without model.type keeps the historical registry fallback.
    assert captured["model_family"] == "gradient_boosted_trees"
    assert captured["validation_outcome"]["error_code"] == "VALIDATION_FAILED"


def test_record_unexpected_failure_uses_request_payload(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        registry_service,
        "persist_research_run_record",
        lambda payload: captured.update(payload) or payload,
    )

    registry_service.record_unexpected_failure(
        run_id="run_123",
        request_id="req_123",
        request_payload={
            "market": "TW",
            "symbols": ["2330"],
            "strategy": {"type": "research_v1", "allow_proactive_sells": True},
            "return_target": "open_to_open",
        },
        rejection_reason="伺服器發生未預期錯誤。",
    )

    assert captured["status"] == "failed"
    assert captured["strategy_type"] == "research_v1"
    assert captured["validation_outcome"] == {"error_code": "INTERNAL_SERVER_ERROR"}
