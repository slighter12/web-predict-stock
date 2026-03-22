from types import SimpleNamespace

import pytest

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
    assert call_order == ["started", "executed", "success"]
