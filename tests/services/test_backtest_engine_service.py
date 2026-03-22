import pandas as pd

import backend.services.backtest_engine_service as backtest_engine_service
from backend.schemas.research_runs import ResearchRunCreateRequest
from backend.strategy_service import ResearchStrategyConfig


def _make_request() -> ResearchRunCreateRequest:
    return ResearchRunCreateRequest(
        runtime_mode="runtime_compatibility_mode",
        market="TW",
        symbols=["2330"],
        date_range={"start": "2024-01-01", "end": "2024-01-04"},
        return_target="open_to_open",
        horizon_days=1,
        features=[{"name": "ma", "window": 5, "source": "close", "shift": 0}],
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


def test_load_symbol_data_includes_peer_features_in_training_frame(monkeypatch):
    request = _make_request()
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
        lambda X, y, test_size: (X.iloc[:3], X.iloc[3:], y.iloc[:3], y.iloc[3:]),
    )

    class _Model:
        def predict(self, X_test):
            return [0.42 for _ in range(len(X_test))]

    monkeypatch.setattr(
        backtest_engine_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Model(),
    )

    result = backtest_engine_service.load_symbol_data(
        "run_123",
        request,
        "2330",
        {"ma": [{"window": 5, "source": "close"}]},
        {"MA_5": 0},
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


def test_execute_research_run_accepts_foundation_version_pack_fields(monkeypatch):
    request = _make_request()
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
        lambda *args, **kwargs: None,
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
    assert exclusion_calls == ["run_foundation_response"]
