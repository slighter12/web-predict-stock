import pandas as pd
import pytest
from pydantic import ValidationError

import backend.research.services.execution as backtest_engine_service
from backend.platform.errors import InsufficientDataError
from backend.research.contracts.runs import (
    ResearchRunCreateRequest,
    ValidationConfig,
    ValidationSummary,
)
from backend.shared.analytics.strategy import ResearchStrategyConfig


def _make_request() -> ResearchRunCreateRequest:
    return ResearchRunCreateRequest(
        runtime_mode="runtime_compatibility_mode",
        market="TW",
        symbols=["2330"],
        date_range={"start": "2024-01-01", "end": "2024-01-04"},
        return_target="open_to_open",
        horizon_days=1,
        features=[{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        model={"type": "random_forest", "params": {}},
        strategy={
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 3,
            "allow_proactive_sells": True,
        },
        execution={"slippage": 0.001, "fees": 0.002},
        baselines=[],
        cluster_snapshot_version="peer_cluster_kmeans_v1",
        peer_policy_version="cluster_nearest_neighbors_v1",
    )


@pytest.mark.parametrize(
    "metrics",
    [{}, {"sharpe": float("nan")}, {"sharpe": float("inf")}, {"sharpe": None}],
)
def test_metrics_finite_check_rejects_invalid_values(metrics):
    assert not backtest_engine_service._metrics_are_finite(metrics)


def test_metrics_finite_check_accepts_flat_result():
    assert backtest_engine_service._metrics_are_finite(
        {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    )


def test_request_rejects_unshifted_daily_features():
    payload = _make_request().model_dump()
    payload["features"][0]["shift"] = 0

    with pytest.raises(ValidationError):
        ResearchRunCreateRequest.model_validate(payload)


def test_direction_model_config_defaults_and_probability_bounds():
    payload = _make_request().model_dump()
    payload["direction_model"] = {"type": "extra_trees", "params": {}}

    request = ResearchRunCreateRequest.model_validate(payload)

    assert request.direction_model.positive_return_threshold == 0.0
    assert request.direction_model.confirmation_probability_threshold == 0.5

    payload["direction_model"]["confirmation_probability_threshold"] = 1.1
    with pytest.raises(ValidationError):
        ResearchRunCreateRequest.model_validate(payload)


def test_load_symbol_data_includes_peer_features_in_training_frame(monkeypatch):
    payload = _make_request().model_dump()
    payload["direction_model"] = {"type": "extra_trees", "params": {}}
    request = ResearchRunCreateRequest.model_validate(payload)
    index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
    raw_df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [1000, 1100, 1200, 1300],
        },
        index=index,
    )

    monkeypatch.setattr(
        backtest_engine_service.data_service,
        "get_data",
        lambda **kwargs: raw_df.copy(),
    )
    monkeypatch.setattr(
        backtest_engine_service.feature_engine,
        "add_features",
        lambda df, feature_config: df.assign(MA_5=[1.0, 2.0, 3.0, 4.0]),
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "materialize_run_factors",
        lambda request, run_id, symbol, df_features: (df_features, []),
    )

    captured: dict[str, object] = {}

    def _fake_prepare_training_data(df, return_target, horizon_days):
        captured["columns"] = list(df.columns)
        captured["peer_symbol_count"] = df["peer_symbol_count_p8"].tolist()
        captured["peer_feature_value"] = df["peer_feature_value_p8"].tolist()
        df_model = df.copy()
        df_model["target"] = [0.01, 0.02, 0.03, 0.04]
        X = df_model[["MA_5", "peer_symbol_count_p8", "peer_feature_value_p8"]]
        y = pd.Series([0.01, 0.02, 0.03, 0.04], index=df_model.index)
        return df_model, X, y

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "prepare_training_data",
        _fake_prepare_training_data,
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "time_series_split",
        lambda X, y, test_size, purge: (
            X.iloc[:3],
            X.iloc[3:],
            y.iloc[:3],
            y.iloc[3:],
        ),
    )

    class _Model:
        def predict(self, X_test):
            return [0.42 for _ in range(len(X_test))]

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Model(),
    )

    class _DirectionModel:
        classes_ = [0, 1]

        def predict_proba(self, X_test):
            return pd.DataFrame([[0.3, 0.7] for _ in range(len(X_test))]).to_numpy()

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (_DirectionModel(), None, 2),
    )

    result = backtest_engine_service.load_symbol_data(
        "run_123",
        request,
        "2330",
        {"ma": [{"window": 5, "source": "close"}]},
        {"MA_5": 1},
        0.25,
        peer_feature_map={
            "2330": {
                pd.Timestamp("2024-01-02"): {
                    "peer_symbol_count_p8": 2.0,
                    "peer_feature_value_p8": 2.0,
                },
                pd.Timestamp("2024-01-04"): {
                    "peer_symbol_count_p8": 1.0,
                    "peer_feature_value_p8": 1.0,
                },
            }
        },
    )

    assert "peer_symbol_count_p8" in captured["columns"]
    assert "peer_feature_value_p8" in captured["columns"]
    assert captured["peer_symbol_count"] == [0.0, 2.0, 2.0, 1.0]
    assert captured["peer_feature_value"] == [0.0, 2.0, 2.0, 1.0]
    assert result["scores"].iloc[0] == 0.42
    assert result["up_probabilities"].iloc[0] == 0.7
    assert result["direction_actuals"].iloc[0] == 1


def test_direction_diagnostics_aggregate_holdout_probabilities():
    payload = _make_request().model_dump()
    payload["direction_model"] = {"type": "extra_trees", "params": {}}
    config = ResearchRunCreateRequest.model_validate(payload).direction_model
    index = pd.to_datetime(["2024-01-03", "2024-01-04"])
    diagnostics = backtest_engine_service.build_direction_classification_diagnostics(
        [
            {
                "symbol": "2330",
                "direction_config": config,
                "direction_unavailable_reason": None,
                "direction_calibration_sample_count": 4,
                "direction_actuals": pd.Series([0, 1], index=index),
                "up_probabilities": pd.Series([0.2, 0.8], index=index),
            }
        ]
    )

    assert diagnostics.evaluation_status == "evaluated"
    assert diagnostics.calibration_policy_version == (
        "chronological_tail_20pct_min20_class5_v1"
    )
    assert diagnostics.confusion_matrix == [[1, 0], [0, 1]]
    assert diagnostics.roc_auc == 1.0
    assert diagnostics.pr_auc == 1.0
    assert diagnostics.brier == pytest.approx(0.04)


def test_direction_diagnostics_fail_closed_for_partial_universe():
    payload = _make_request().model_dump()
    payload["direction_model"] = {"type": "extra_trees", "params": {}}
    config = ResearchRunCreateRequest.model_validate(payload).direction_model

    diagnostics = backtest_engine_service.build_direction_classification_diagnostics(
        [
            {
                "symbol": "2330",
                "direction_config": config,
                "direction_unavailable_reason": None,
                "direction_calibration_sample_count": 4,
                "direction_actuals": pd.Series([0, 1]),
                "up_probabilities": pd.Series([0.2, 0.8]),
            },
            {
                "symbol": "2317",
                "direction_config": config,
                "direction_unavailable_reason": (
                    "Direction model calibration window requires both classes."
                ),
                "direction_calibration_sample_count": 0,
            },
        ]
    )

    assert diagnostics.evaluation_status == "not_evaluated"
    assert "2317" in diagnostics.status_reason
    assert diagnostics.confusion_matrix == []


def test_execute_research_run_accepts_foundation_version_pack_fields(monkeypatch):
    request = _make_request()
    request.baselines = ["buy_and_hold", "naive_momentum"]
    request.validation = ValidationConfig(
        method="holdout", splits=1, test_size=0.25
    )
    request.factor_catalog_version = "catalog_manual_v1"
    request.scoring_factor_ids = [
        "company_listing_age_days_v1",
        "important_event_count_30d_v1",
    ]
    request.external_signal_policy_version = "tw_company_event_layer_v1"
    request.execution_route = "research_only"
    request.adaptive_mode = "shadow"
    request.adaptive_profile_id = "adaptive_shadow_v1"
    request.reward_definition_version = "reward_v1"
    request.state_definition_version = "state_v1"
    request.rollout_control_version = "rollout_v1"

    monkeypatch.setattr(
        backtest_engine_service,
        "resolve_runtime_strategy",
        lambda **kwargs: {
            "strategy": ResearchStrategyConfig(
                type="research_v1",
                threshold=0.003,
                top_n=3,
                allow_proactive_sells=True,
            ),
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
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "build_run_foundation_context",
        lambda request: (
            {
                "factor_catalog_version": request.factor_catalog_version,
                "scoring_factor_ids": request.scoring_factor_ids,
                "external_signal_policy_version": request.external_signal_policy_version,
                "external_lineage_version": "tw_company_event_lineage_v1",
                "cluster_snapshot_version": request.cluster_snapshot_version,
                "peer_policy_version": request.peer_policy_version,
                "peer_comparison_policy_version": "peer_relative_overlay_v1",
                "execution_route": request.execution_route,
                "simulation_profile_id": None,
                "simulation_adapter_version": None,
                "live_control_profile_id": None,
                "live_control_version": None,
                "adaptive_mode": request.adaptive_mode,
                "adaptive_profile_id": request.adaptive_profile_id,
                "adaptive_contract_version": "adaptive_isolation_contract_v1",
                "reward_definition_version": request.reward_definition_version,
                "state_definition_version": request.state_definition_version,
                "rollout_control_version": request.rollout_control_version,
            },
            [],
        ),
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "build_run_peer_feature_map",
        lambda request: {},
    )
    sample_index = pd.to_datetime(["2024-01-03"])
    monkeypatch.setattr(
        backtest_engine_service,
        "load_symbol_data",
        lambda *args, **kwargs: {
            "symbol": args[2],
            "df_model": pd.DataFrame(
                {
                    "open": [100.0],
                    "high": [101.0],
                    "low": [99.0],
                    "close": [100.5],
                    "volume": [1000],
                },
                index=sample_index,
            ),
            "X": pd.DataFrame({"MA_5": [1.0]}, index=sample_index),
            "y": pd.Series([0.01], index=sample_index),
            "scores": pd.Series([0.42], index=sample_index, name=args[2]),
            "open": pd.Series([100.0], index=sample_index, name=args[2]),
            "high": pd.Series([101.0], index=sample_index, name=args[2]),
            "low": pd.Series([99.0], index=sample_index, name=args[2]),
            "close": pd.Series([100.5], index=sample_index, name=args[2]),
            "volume": pd.Series([1000], index=sample_index, name=args[2]),
            "factor_materializations": [],
        },
    )
    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "build_target_weights",
        lambda scores, strategy: pd.DataFrame(
            1.0 / len(scores.columns), index=scores.index, columns=scores.columns
        ),
    )
    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest",
        lambda **kwargs: (
            {
                "total_return": 0.12,
                "sharpe": 1.1,
                "max_drawdown": -0.08,
                "turnover": 0.3,
            },
            [{"date": "2024-01-03", "equity": 1.0}],
            [{"date": "2024-01-03", "symbol": "2330", "score": 0.42, "position": 1.0}],
            [],
        ),
    )
    monkeypatch.setitem(
        backtest_engine_service.baseline_service.BASELINE_BUILDERS,
        "buy_and_hold",
        lambda close: pd.DataFrame(1.0, index=close.index, columns=close.columns),
    )
    monkeypatch.setitem(
        backtest_engine_service.baseline_service.BASELINE_BUILDERS,
        "naive_momentum",
        lambda close: pd.DataFrame(0.5, index=close.index, columns=close.columns),
    )

    def _run_baseline(weights, **kwargs):
        if weights.iloc[0, 0] == 1.0:
            return {"sharpe": float("nan")}, []
        return {"sharpe": 0.5}, []

    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest_from_weights",
        _run_baseline,
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "build_p3_summary",
        lambda **kwargs: {
            "corporate_event_state": "clear",
            "investability_screening_active": False,
            "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
            "adv_basis_version": "raw_close_x_volume_active_session_v1",
            "missing_feature_policy_version": "xgboost_native_missing_v1",
            "execution_cost_model_version": "fees_slippage_only_v1",
            "tradability_state": "execution_ready",
            "tradability_contract_version": "p3_tradability_monitoring_v1",
            "capacity_screening_active": False,
            "missing_feature_policy_state": "native_missing_supported",
            "full_universe_count": 3,
            "execution_universe_count": 3,
            "execution_universe_ratio": 1.0,
            "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
            "liquidity_bucket_coverages": [],
            "stale_mark_days_with_open_positions": 0,
            "stale_risk_share": 0.0,
            "monitor_observation_status": "persisted",
        },
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "compute_validation_summary",
        lambda *args, **kwargs: ValidationSummary(
            method="holdout",
            evaluation_status="not_evaluated",
            status_reason="common-date sample is insufficient",
            metrics={},
        ),
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "build_forward_opinion_signals",
        lambda *args, **kwargs: ([], "prospective snapshot is unavailable"),
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "persist_run_factor_observations",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "persist_run_peer_outputs",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        backtest_engine_service,
        "dispatch_run_execution_route",
        lambda **kwargs: [],
    )
    exclusion_calls: list[str] = []
    monkeypatch.setattr(
        backtest_engine_service,
        "record_run_adaptive_exclusion",
        lambda run_id: exclusion_calls.append(run_id),
    )

    artifacts = backtest_engine_service.execute_research_run(
        "run_foundation_response",
        request,
    )

    assert artifacts.response.run_id == "run_foundation_response"
    assert artifacts.response.factor_catalog_version == "catalog_manual_v1"
    assert artifacts.response.peer_policy_version == "cluster_nearest_neighbors_v1"
    assert artifacts.response.adaptive_mode == "shadow"
    assert artifacts.response.reward_definition_version == "reward_v1"
    assert artifacts.response.comparison_eligibility == "research_only_comparable"
    assert artifacts.response.baselines == {"naive_momentum": {"sharpe": 0.5}}
    assert artifacts.response.warnings == [
        "prospective snapshot is unavailable",
        "Baseline 'buy_and_hold' not evaluated: backtest produced empty or "
        "non-finite metrics.",
        "Validation not evaluated: common-date sample is insufficient",
    ]
    assert artifacts.warnings == artifacts.response.warnings
    assert exclusion_calls == ["run_foundation_response"]

    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest",
        lambda **kwargs: ({"sharpe": float("nan")}, [], [], []),
    )
    with pytest.raises(
        InsufficientDataError,
        match="Main backtest produced empty or non-finite metrics",
    ):
        backtest_engine_service.execute_research_run("run_non_finite", request)


def test_forward_opinion_requires_same_latest_date_and_complete_universe(monkeypatch):
    request = _make_request()
    request.symbols = ["2330", "2317"]
    request = ResearchRunCreateRequest.model_validate(
        {
            **request.model_dump(mode="json"),
            "direction_model": {"type": "extra_trees", "params": {}},
        }
    )
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])

    class _Regressor:
        def predict(self, frame):
            return [0.02]

    class _Classifier:
        classes_ = [0, 1]

        def predict_proba(self, frame):
            return [[0.2, 0.8]]

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (_Classifier(), None, 1),
    )
    symbol_data = [
        {
            "symbol": symbol,
            "X": pd.DataFrame({"MA_5": [1.0]}, index=index[:1]),
            "y": pd.Series([0.01], index=index[:1]),
            "prediction_features": pd.DataFrame(
                {"MA_5": [1.0, 2.0]}, index=index
            ),
        }
        for symbol in ("2330", "2317")
    ]
    strategy = ResearchStrategyConfig(
        type="research_v1", threshold=0.003, top_n=1, allow_proactive_sells=True
    )

    signals, warning = backtest_engine_service.build_forward_opinion_signals(
        symbol_data, request, strategy
    )

    assert warning is None
    assert {item["symbol"] for item in signals} == {"2330", "2317"}
    assert {item["date"] for item in signals} == {index[-1].date()}
    assert all(item["signal_kind"] == "forward_opinion" for item in signals)
    symbol_data[1]["prediction_features"] = symbol_data[1][
        "prediction_features"
    ].iloc[:-1]
    signals, warning = backtest_engine_service.build_forward_opinion_signals(
        symbol_data, request, strategy
    )
    assert signals == []
    assert "do not share one latest feature date" in warning


def test_forward_opinion_fails_closed_for_zero_lookahead_target():
    payload = _make_request().model_dump(mode="json")
    payload.update(
        return_target="open_to_close",
        direction_model={"type": "extra_trees", "params": {}},
    )
    request = ResearchRunCreateRequest.model_validate(payload)

    signals, warning = backtest_engine_service.build_forward_opinion_signals(
        [{}],
        request,
        ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
    )
    assert signals == []
    assert "no unlabeled forward feature row" in warning


def test_forward_opinion_reports_direction_calibration_failure(monkeypatch):
    payload = _make_request().model_dump(mode="json")
    payload["direction_model"] = {"type": "extra_trees", "params": {}}
    request = ResearchRunCreateRequest.model_validate(payload)
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    symbol_data = [
        {
            "symbol": "2330",
            "X": pd.DataFrame({"MA_5": [1.0]}, index=index[:1]),
            "y": pd.Series([0.01], index=index[:1]),
            "prediction_features": pd.DataFrame(
                {"MA_5": [1.0, 2.0]}, index=index
            ),
        }
    ]
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (None, "class support unavailable", 0),
    )

    signals, warning = backtest_engine_service.build_forward_opinion_signals(
        symbol_data, request, request.strategy
    )

    assert signals == []
    assert warning == (
        "[2330] Prospective direction calibration unavailable: "
        "class support unavailable"
    )


def test_holdout_confirmation_fails_closed_for_partial_universe():
    payload = _make_request().model_dump(mode="json")
    payload.update(
        symbols=["2330", "2317"],
        direction_model={
            "type": "extra_trees",
            "params": {},
            "confirmation_probability_threshold": 0.0,
        },
    )
    request = ResearchRunCreateRequest.model_validate(payload)
    index = pd.to_datetime(["2024-01-03", "2024-01-04"])
    scores = pd.DataFrame(
        {"2330": [0.01, 0.02], "2317": [0.03, 0.04]}, index=index
    )

    probabilities, warning = (
        backtest_engine_service.build_holdout_confirmation_probabilities(
            [
                {
                    "symbol": "2330",
                    "up_probabilities": pd.Series([0.8, 0.9], index=index),
                },
                {"symbol": "2317"},
            ],
            scores,
            request,
        )
    )

    assert probabilities.isna().all().all()
    assert "2317" in warning
    weights = backtest_engine_service.backtest_service.build_target_weights(
        scores=scores,
        strategy=request.strategy,
        confirmation_probabilities=probabilities,
        confirmation_threshold=0.0,
    )
    assert (weights == 0.0).all().all()


def _validation_request(*, direction: bool) -> ResearchRunCreateRequest:
    payload = _make_request().model_dump(mode="json")
    payload["validation"] = {"method": "holdout", "splits": 1, "test_size": 0.25}
    if direction:
        payload["direction_model"] = {"type": "extra_trees", "params": {}}
    return ResearchRunCreateRequest.model_validate(payload)


def _validation_symbol_data() -> list[dict]:
    index = pd.date_range("2024-01-01", periods=6)
    prices = pd.DataFrame(
        {
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.5] * 6,
        },
        index=index,
    )
    return [
        {
            "symbol": "2330",
            "df_model": prices,
            "X": pd.DataFrame({"MA_5": range(6)}, index=index),
            "y": pd.Series([-0.02, 0.01, -0.01, 0.02, 0.01, -0.01], index=index),
        }
    ]


def test_validation_uses_calibrated_direction_probabilities(monkeypatch):
    request = _validation_request(direction=True)
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 4), range(4, 6))],
    )

    class _Regressor:
        def predict(self, frame):
            return [0.02] * len(frame)

    class _Classifier:
        classes_ = [0, 1]

        def predict_proba(self, frame):
            return pd.DataFrame([[0.2, 0.8]] * len(frame)).to_numpy()

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (_Classifier(), None, 2),
    )
    captured = {}

    def _run_backtest(**kwargs):
        captured.update(kwargs)
        return {"sharpe": 1.0}, [], [], []

    monkeypatch.setattr(
        backtest_engine_service.backtest_service, "run_backtest", _run_backtest
    )

    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(),
        request,
        request.strategy,
    )

    assert captured["confirmation_probabilities"]["2330"].tolist() == [0.8, 0.8]
    assert summary.evaluation_status == "evaluated"
    assert summary.status_reason is None
    assert summary.metrics == {"sharpe": 1.0, "avg_sharpe": 1.0}


def test_validation_fails_closed_when_direction_calibration_is_unavailable(
    monkeypatch,
):
    request = _validation_request(direction=True)
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 4), range(4, 6))],
    )

    class _Regressor:
        def predict(self, frame):
            return [0.02] * len(frame)

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (None, "calibration unavailable", 0),
    )
    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest",
        lambda **kwargs: pytest.fail("hybrid validation must not fall back"),
    )

    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(),
        request,
        request.strategy,
    )

    assert summary.evaluation_status == "not_evaluated"
    assert summary.metrics == {}
    assert "calibration unavailable" in summary.status_reason


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), 1.01])
def test_validation_reports_invalid_direction_probabilities(
    monkeypatch, probability
):
    request = _validation_request(direction=True)
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 4), range(4, 6))],
    )

    class _Regressor:
        def predict(self, frame):
            return [0.02] * len(frame)

    class _Classifier:
        classes_ = [0, 1]

        def predict_proba(self, frame):
            return pd.DataFrame(
                [[1.0 - probability, probability] for _ in range(len(frame))]
            ).to_numpy()

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (_Classifier(), None, 2),
    )
    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest",
        lambda **kwargs: pytest.fail("invalid probabilities must not be backtested"),
    )

    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(), request, request.strategy
    )

    assert summary.evaluation_status == "not_evaluated"
    assert "outside [0, 1]" in summary.status_reason


def test_validation_keeps_regression_only_behavior(monkeypatch):
    request = _validation_request(direction=False)
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 4), range(4, 6))],
    )

    class _Regressor:
        def predict(self, frame):
            return [0.02] * len(frame)

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    captured = {}

    def _run_backtest(**kwargs):
        captured.update(kwargs)
        return {"sharpe": 1.0}, [], [], []

    monkeypatch.setattr(
        backtest_engine_service.backtest_service, "run_backtest", _run_backtest
    )

    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(),
        request,
        request.strategy,
    )

    assert captured["confirmation_probabilities"] is None
    assert summary.evaluation_status == "evaluated"
    assert summary.metrics == {"sharpe": 1.0, "avg_sharpe": 1.0}

    monkeypatch.setattr(
        backtest_engine_service.backtest_service,
        "run_backtest",
        lambda **kwargs: ({"sharpe": float("inf")}, [], [], []),
    )
    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(), request, request.strategy
    )
    assert summary.evaluation_status == "not_evaluated"
    assert "non-finite metrics" in summary.status_reason


def test_validation_backtests_complete_cross_section_once_per_fold(monkeypatch):
    payload = _validation_request(direction=False).model_dump(mode="json")
    payload["symbols"] = ["2330", "2317"]
    payload["strategy"]["top_n"] = 1
    request = ResearchRunCreateRequest.model_validate(payload)
    symbol_data = _validation_symbol_data()
    second = {
        **symbol_data[0],
        "symbol": "2317",
        "df_model": symbol_data[0]["df_model"].copy(),
        "X": symbol_data[0]["X"].copy(),
        "y": symbol_data[0]["y"].copy(),
    }
    symbol_data.append(second)
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 4), range(4, 6))],
    )

    prediction = iter((0.01, 0.02))

    class _Regressor:
        def __init__(self, value):
            self.value = value

        def predict(self, frame):
            return [self.value] * len(frame)

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(next(prediction)),
    )
    calls = []

    def _run_backtest(**kwargs):
        calls.append(kwargs)
        weights = backtest_engine_service.backtest_service.build_target_weights(
            scores=kwargs["scores"], strategy=kwargs["strategy"]
        )
        assert (weights.gt(0).sum(axis=1) == 1).all()
        return {"sharpe": 1.5}, [], [], []

    monkeypatch.setattr(
        backtest_engine_service.backtest_service, "run_backtest", _run_backtest
    )

    summary = backtest_engine_service.compute_validation_summary(
        symbol_data, request, request.strategy
    )

    assert len(calls) == 1
    assert list(calls[0]["scores"].columns) == ["2330", "2317"]
    assert summary.evaluation_status == "evaluated"
    assert summary.metrics == {"sharpe": 1.5, "avg_sharpe": 1.5}


def test_validation_uses_common_dates_for_misaligned_symbol_calendars(monkeypatch):
    payload = _validation_request(direction=False).model_dump(mode="json")
    payload["symbols"] = ["2330", "2317"]
    request = ResearchRunCreateRequest.model_validate(payload)
    first = _validation_symbol_data()[0]
    second = {
        **first,
        "symbol": "2317",
        "df_model": first["df_model"].drop(index=first["X"].index[1]),
        "X": first["X"].drop(index=first["X"].index[1]),
        "y": first["y"].drop(index=first["X"].index[1]),
    }
    monkeypatch.setattr(
        backtest_engine_service.validation_service,
        "generate_splits",
        lambda **kwargs: [(range(0, 3), range(3, 5))],
    )

    class _Regressor:
        def predict(self, frame):
            return [0.02] * len(frame)

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(),
    )
    calls = []

    def _run_backtest(**kwargs):
        calls.append(kwargs)
        return {"sharpe": 1.0}, [], [], []

    monkeypatch.setattr(
        backtest_engine_service.backtest_service, "run_backtest", _run_backtest
    )

    summary = backtest_engine_service.compute_validation_summary(
        [first, second], request, request.strategy
    )

    expected_dates = first["X"].index.drop(first["X"].index[1])[-2:]
    assert summary.evaluation_status == "evaluated"
    assert calls[0]["scores"].index.equals(expected_dates)
    assert all(
        frame.index.equals(expected_dates)
        for frame in calls[0].values()
        if isinstance(frame, pd.DataFrame)
    )


def test_validation_reports_no_common_dates_without_raising():
    payload = _validation_request(direction=False).model_dump(mode="json")
    payload["symbols"] = ["2330", "2317"]
    request = ResearchRunCreateRequest.model_validate(payload)
    first = _validation_symbol_data()[0]
    second_index = pd.date_range("2025-01-01", periods=6)
    second = {
        **first,
        "symbol": "2317",
        "df_model": first["df_model"].set_axis(second_index),
        "X": first["X"].set_axis(second_index),
        "y": first["y"].set_axis(second_index),
    }

    summary = backtest_engine_service.compute_validation_summary(
        [first, second], request, request.strategy
    )

    assert summary.evaluation_status == "not_evaluated"
    assert summary.metrics == {}
    assert "no common model-ready dates" in summary.status_reason


def test_validation_reports_partial_requested_universe_without_raising():
    payload = _validation_request(direction=False).model_dump(mode="json")
    payload["symbols"] = ["2330", "2317"]
    request = ResearchRunCreateRequest.model_validate(payload)

    summary = backtest_engine_service.compute_validation_summary(
        _validation_symbol_data(), request, request.strategy
    )

    assert summary.evaluation_status == "not_evaluated"
    assert summary.metrics == {}
    assert "does not match the requested universe" in summary.status_reason
