from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import backend.api.research_runs as research_runs_api
import backend.app as backend_app
from backend.app import app
from backend.domain.runtime_bundle import build_version_pack_payload
from backend.errors import DataAccessError, UnsupportedConfigurationError
from backend.schemas.research_runs import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)

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


def test_create_research_run_validation_failed(monkeypatch):
    monkeypatch.setattr(
        backend_app, "persist_request_research_run", lambda *args, **kwargs: True
    )
    payload = make_payload()
    payload["symbols"] = ["2330", "2330"]

    response = client.post("/api/v1/research/runs", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.json()["meta"]["request_id"]
    assert response.json()["meta"]["run_id"]


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
