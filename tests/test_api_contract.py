import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.api_models import BacktestRequest
from backend.errors import DataNotFoundError, InsufficientDataError


def make_payload() -> dict:
    return {
        "market": "TW",
        "symbols": ["2330"],
        "date_range": {"start": "2022-01-01", "end": "2024-01-01"},
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": [
            {"name": "ma", "window": 5, "source": "close", "shift": 1},
        ],
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


def fake_symbol_data() -> dict:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    df_model = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
        },
        index=idx,
    )
    return {
        "symbol": "2330",
        "df_model": df_model,
        "X": pd.DataFrame({"MA_5": [1.0, 2.0]}, index=idx),
        "y": pd.Series([0.01, 0.02], index=idx),
        "scores": pd.Series([0.01, 0.02], index=idx, name="2330"),
        "open": df_model["open"].rename("2330"),
        "high": df_model["high"].rename("2330"),
        "low": df_model["low"].rename("2330"),
        "close": df_model["close"].rename("2330"),
    }


def test_backtest_endpoint_success(monkeypatch):
    monkeypatch.setattr(main, "_load_symbol_data", lambda *args, **kwargs: fake_symbol_data())
    monkeypatch.setattr(
        main.backtest_service,
        "run_backtest",
        lambda **kwargs: (
            {
                "total_return": 0.12,
                "sharpe": 1.1,
                "max_drawdown": -0.08,
                "turnover": 0.3,
            },
            [{"date": pd.Timestamp("2024-01-02").date(), "equity": 1.0}],
            [{"date": pd.Timestamp("2024-01-02").date(), "symbol": "2330", "score": 0.01, "position": 1.0}],
            [],
        ),
    )

    client = TestClient(main.app)
    response = client.post("/api/v1/backtest", json=make_payload())
    result = response.json()

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]
    assert result["metrics"]["total_return"] == 0.12
    assert result["signals"][0]["symbol"] == "2330"
    assert result["warnings"] == []


def test_compute_validation_summary_adds_avg_sharpe(monkeypatch):
    request_payload = make_payload()
    request_payload["validation"] = {"method": "walk_forward", "splits": 2, "test_size": 0.5}
    request = BacktestRequest(**request_payload)

    monkeypatch.setattr(
        main.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 1), range(1, 2)), (range(0, 1), range(1, 2))],
    )

    class DummyModel:
        def predict(self, X):
            return [0.01] * len(X)

    monkeypatch.setattr(
        main.model_service,
        "fit_xgboost_regressor",
        lambda *args, **kwargs: DummyModel(),
    )

    metrics_sequence = [
        {"total_return": 0.10, "sharpe": 0.8, "max_drawdown": -0.05, "turnover": 0.2},
        {"total_return": 0.20, "sharpe": 1.0, "max_drawdown": -0.07, "turnover": 0.4},
    ]

    def fake_run_backtest(**kwargs):
        return metrics_sequence.pop(0), [], [], []

    monkeypatch.setattr(main.backtest_service, "run_backtest", fake_run_backtest)

    summary = main.compute_validation_summary([fake_symbol_data()], request)

    assert summary is not None
    assert summary.metrics["sharpe"] == pytest.approx(0.9)
    assert summary.metrics["avg_sharpe"] == pytest.approx(0.9)


def test_backtest_request_invalid_strategy_type():
    payload = make_payload()
    payload["strategy"]["type"] = "bad_strategy"

    with pytest.raises(ValidationError):
        BacktestRequest(**payload)


def test_backtest_request_invalid_market():
    payload = make_payload()
    payload["market"] = "JP"

    with pytest.raises(ValidationError):
        BacktestRequest(**payload)


def test_backtest_endpoint_symbol_not_found(monkeypatch):
    def fake_load(*args, **kwargs):
        raise DataNotFoundError("No data found for symbol '2330' in the specified date range.")

    monkeypatch.setattr(main, "_load_symbol_data", fake_load)

    client = TestClient(main.app)
    response = client.post("/api/v1/backtest", json=make_payload())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "No data found for symbol" in response.json()["error"]["message"]
    assert response.json()["meta"]["request_id"]


def test_backtest_endpoint_insufficient_data(monkeypatch):
    def fake_load(*args, **kwargs):
        raise InsufficientDataError("[2330] Not enough data to create a train/test split with test_size=0.2.")

    monkeypatch.setattr(main, "_load_symbol_data", fake_load)

    client = TestClient(main.app)
    response = client.post("/api/v1/backtest", json=make_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"
    assert "Not enough data" in response.json()["error"]["message"]
