from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import backend.app as backend_app
import backend.research.api as research_runs_api
from backend.app import app
from backend.platform.errors import DataAccessError, UnsupportedConfigurationError
from backend.research.contracts.runs import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)
from backend.research.domain.version_pack import build_version_pack_payload

client = TestClient(app)


def make_payload() -> dict:
    return {
        "runtime_mode": "runtime_compatibility_mode",
        "market": "TW",
        "symbols": ["2330"],
        "date_range": {"start": "2022-01-01", "end": "2024-01-01"},
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": [{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        "model": {"type": "xgboost", "params": {}},
        "strategy": {
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 3,
            "allow_proactive_sells": True,
        },
        "execution": {"slippage": 0.001, "fees": 0.002},
        "baselines": [],
    }


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
            }
        ),
    )


def make_record(run_id: str = "run_123") -> ResearchRunRecordResponse:
    return ResearchRunRecordResponse(
        run_id=run_id,
        request_id="req_123",
        status="succeeded",
        market="TW",
        symbols=["2330"],
        strategy_type="research_v1",
        runtime_mode="runtime_compatibility_mode",
        default_bundle_version=None,
        effective_strategy=EffectiveStrategyConfig(threshold=0.003, top_n=3),
        allow_proactive_sells=True,
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
        validation_outcome={"ok": True},
        rejection_reason=None,
        request_payload=make_payload(),
        metrics=Metrics(
            total_return=0.12, sharpe=1.1, max_drawdown=-0.08, turnover=0.3
        ),
        warnings=[],
        created_at=datetime.now(timezone.utc),
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
            }
        ),
    )


def test_create_research_run_success(monkeypatch):
    monkeypatch.setattr(
        research_runs_api, "create_research_run", lambda **kwargs: make_response()
    )

    response = client.post("/api/v1/research/runs", json=make_payload())

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]
    assert response.json()["run_id"] == "run_123"
    assert response.json()["metrics"]["total_return"] == 0.12


def test_create_backtest_returns_full_research_run_response(monkeypatch):
    monkeypatch.setattr(
        research_runs_api, "create_research_run", lambda **kwargs: make_response()
    )

    response = client.post("/api/v1/backtest", json=make_payload())

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_123"
    assert response.json()["runtime_mode"] == "runtime_compatibility_mode"
    assert response.json()["effective_strategy"]["threshold"] == 0.003
    assert (
        response.json()["threshold_policy_version"] == "static_absolute_gross_label_v1"
    )


def test_create_research_run_validation_failed(monkeypatch):
    captured: dict = {}

    def capture_record_validation_failure(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(
        backend_app,
        "record_validation_failure",
        capture_record_validation_failure,
    )
    payload = make_payload()
    payload["symbols"] = ["2330", "2330"]

    response = client.post("/api/v1/research/runs", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.json()["meta"]["request_id"]
    assert response.json()["meta"]["run_id"]
    assert captured["run_id"] == response.json()["meta"]["run_id"]
    assert captured["details"]["fields"]


def test_create_research_run_validation_failed_omits_run_id_on_registry_failure(
    monkeypatch,
):
    def raise_data_access_error(**kwargs):
        raise DataAccessError("db unavailable")

    monkeypatch.setattr(
        backend_app,
        "record_validation_failure",
        raise_data_access_error,
    )
    payload = make_payload()
    payload["symbols"] = ["2330", "2330"]

    response = client.post("/api/v1/research/runs", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "run_id" not in response.json()["meta"]


def test_create_research_run_rejected(monkeypatch):
    def raise_rejected(**kwargs):
        raise UnsupportedConfigurationError("bad research run")

    monkeypatch.setattr(research_runs_api, "create_research_run", raise_rejected)

    response = client.post("/api/v1/research/runs", json=make_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_CONFIGURATION"
    assert response.json()["error"]["message"] == "bad research run"


def test_create_research_run_data_access_failed(monkeypatch):
    def raise_data_access(**kwargs):
        raise DataAccessError("db unavailable")

    monkeypatch.setattr(research_runs_api, "create_research_run", raise_data_access)

    response = client.post("/api/v1/research/runs", json=make_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATA_ACCESS_FAILED"


def test_create_research_run_unexpected_failed(monkeypatch):
    captured: dict = {}

    def raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    def capture_record_unexpected_failure(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(research_runs_api, "create_research_run", raise_unexpected)
    monkeypatch.setattr(
        backend_app,
        "record_unexpected_failure",
        capture_record_unexpected_failure,
    )
    local_client = TestClient(app, raise_server_exceptions=False)

    response = local_client.post("/api/v1/research/runs", json=make_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert response.json()["meta"]["request_id"]
    assert response.json()["meta"]["run_id"]
    assert captured["run_id"] == response.json()["meta"]["run_id"]
    assert captured["rejection_reason"] == "伺服器發生未預期錯誤。"


def test_create_research_run_unexpected_failed_omits_run_id_on_registry_failure(
    monkeypatch,
):
    def raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    def raise_data_access_error(**kwargs):
        raise DataAccessError("db unavailable")

    monkeypatch.setattr(research_runs_api, "create_research_run", raise_unexpected)
    monkeypatch.setattr(
        backend_app,
        "record_unexpected_failure",
        raise_data_access_error,
    )
    local_client = TestClient(app, raise_server_exceptions=False)

    response = local_client.post("/api/v1/research/runs", json=make_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "run_id" not in response.json()["meta"]


def test_get_research_run(monkeypatch):
    monkeypatch.setattr(
        research_runs_api, "get_research_run", lambda run_id: make_record(run_id)
    )

    response = client.get("/api/v1/research/runs/run_abc")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_abc"
    assert response.json()["status"] == "succeeded"


def test_list_research_runs(monkeypatch):
    monkeypatch.setattr(
        research_runs_api,
        "list_research_runs",
        lambda: [make_record("run_a"), make_record("run_b")],
    )

    response = client.get("/api/v1/research/runs")

    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()] == ["run_a", "run_b"]


def test_read_p3_gate(monkeypatch):
    monkeypatch.setattr(
        research_runs_api,
        "get_p3_phase_gate_summary",
        lambda: {
            "gate_id": "GATE-P3-001",
            "verification_gate_id": "GATE-VERIFICATION-001",
            "overall_status": "pass",
            "metrics": {
                "KPI-RESEARCH-004": {
                    "value": 1.0,
                    "status": "pass",
                    "numerator": 20.0,
                    "denominator": 20.0,
                    "unit": None,
                    "window": "rolling 20 runs",
                    "details": {},
                }
            },
            "artifacts": {
                "lifecycle_aware_execution_universe": {
                    "status": "pass",
                    "details": {"latest_run_id": "run_123"},
                }
            },
            "missing_reasons": [],
        },
    )

    response = client.get("/api/v1/research/gates/p3")

    assert response.status_code == 200
    assert response.json()["gate_id"] == "GATE-P3-001"
    assert response.json()["metrics"]["KPI-RESEARCH-004"]["status"] == "pass"


def test_read_micro_kpis(monkeypatch):
    monkeypatch.setattr(
        research_runs_api,
        "get_micro_kpi_summary",
        lambda market="TW": {
            "gate_id": "GATE-P3-OPS-001",
            "overall_status": "pass",
            "metrics": {
                "KPI-MICRO-001": {
                    "value": 0.8,
                    "status": "pass",
                    "numerator": None,
                    "denominator": None,
                    "unit": None,
                    "window": "20 active trading days + 60 baseline trading days",
                    "details": {},
                }
            },
            "selection_policy": {
                "monitor_profile_id": "p3_monitor_default_v1",
                "market": market,
            },
            "binding_status": "monitoring",
            "binding_reason": None,
        },
    )

    response = client.get("/api/v1/research/micro-kpis?market=TW")

    assert response.status_code == 200
    assert response.json()["gate_id"] == "GATE-P3-OPS-001"
    assert response.json()["selection_policy"]["market"] == "TW"
