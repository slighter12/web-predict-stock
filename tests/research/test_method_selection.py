from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.research.api as research_api
import backend.research.repositories.method_selection as method_selection_repository
import backend.research.repositories.runs as research_run_repository
import backend.research.services.run_projection as research_run_projection
import backend.research.services.registry as registry_service
import backend.research.services.method_selection as service
from backend.app import app
from backend.database import (
    Base,
    MethodSelectionMatrix,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)
from backend.platform.errors import (
    CalibrationBusyError,
    CalibrationEvaluationError,
    DataAccessError,
    InsufficientDataError,
)
from backend.research.contracts.calibration import CalibrationCandidateFoldResult
from backend.research.contracts.method_selection import (
    MethodCandidateSummary,
    MethodSelectionFeatureSetManifest,
    MethodSelectionFoldBoundary,
    MethodSelectionMatrixCreateRequest,
    MethodSelectionMatrixResponse,
)
from backend.research.contracts.runs import ResearchRunResponse
from backend.research.contracts.runs import DateRange
from backend.research.contracts.runs import StrategyConfig
from backend.research.contracts.runtime_metadata import EffectiveStrategyConfig
from backend.research.domain.version_pack import build_version_pack_payload
from backend.shared.analytics.pooled import (
    PooledModelReadyDataset,
    build_market_date_folds,
)
from backend.shared.analytics.models import ModelUnavailableError

client = TestClient(app)


def _request() -> MethodSelectionMatrixCreateRequest:
    return MethodSelectionMatrixCreateRequest(
        symbols=["AAA", "BBB"],
        date_range={"start": "2020-01-01", "end": "2024-12-31"},
        horizon_days=5,
        model_families=["extra_trees"],
    )


def test_feature_screening_has_baseline_add_full_and_remove_arms():
    feature_sets, specs = service.build_feature_set_manifests()

    assert len(feature_sets) == 18
    assert feature_sets[0].feature_set_id == "baseline"
    assert {x.feature_set_id for x in feature_sets} >= {
        "full", "baseline_plus_macd", "full_without_macd",
    }
    assert len(specs["baseline"]) == 6
    assert len(specs["full"]) == 21


def test_dynamic_threshold_contract_requires_policy_and_no_numeric_placeholder():
    policy = {
        "policy_version": "threshold-policy",
        "return_target": "open_to_open",
        "horizon_days": 5,
        "lookback": 20,
        "multiplier": 0.5,
        "estimator": "sample_standard_deviation",
        "ddof": 1,
        "complete_window_required": True,
        "continuity_policy_version": "continuity-policy",
        "horizon_scaling": "square_root",
    }

    strategy = StrategyConfig(
        threshold=None,
        top_n=5,
        threshold_mode="dynamic",
        dynamic_threshold_policy=policy,
    )
    effective = EffectiveStrategyConfig(
        threshold=None,
        top_n=5,
        threshold_mode="dynamic",
        dynamic_threshold_policy=policy,
    )

    assert strategy.dynamic_threshold_policy is not None
    assert effective.threshold is None
    with pytest.raises(ValueError, match="numeric threshold"):
        StrategyConfig(
            threshold=0.0,
            top_n=5,
            threshold_mode="dynamic",
            dynamic_threshold_policy=policy,
        )
    with pytest.raises(ValueError, match="policy metadata"):
        EffectiveStrategyConfig(
            threshold=None,
            top_n=5,
            threshold_mode="dynamic",
        )


def test_phase_a_is_fixed_and_phase_b_searches_only_one_feature_set():
    sets, _ = service.build_feature_set_manifests()
    screening = service.build_screening_candidate_manifests(_request(), sets)
    tuning = service.build_tuning_candidate_manifests(_request(), sets[0])

    assert len(screening) == 18
    assert {(x.model_type, x.capacity_preset, x.volatility_lookback, x.multiplier, x.top_n) for x in screening} == {("extra_trees", "balanced", 60, 0.75, 10)}
    assert len(tuning) == 3 * 3 * 3 * 3
    assert {x.feature_set_id for x in tuning} == {"baseline"}


def test_nested_fold_dates_are_disjoint_from_outer_and_final_holdout():
    dates = tuple(date(2018, 1, 1) + timedelta(days=index) for index in range(1000))
    selection, final = dates[:-252], dates[-252:]
    outer = build_market_date_folds(selection, splits=5, test_size=0.1, purge=5)

    for outer_fold in outer:
        inner = build_market_date_folds(outer_fold.train_dates, splits=3, test_size=0.2, purge=5)
        outer_holdout = set(outer_fold.holdout_dates)
        for inner_fold in inner:
            assert set(inner_fold.train_dates).isdisjoint(inner_fold.holdout_dates)
            assert set(inner_fold.holdout_dates).isdisjoint(outer_holdout)
            assert set(inner_fold.train_dates).isdisjoint(final)
            assert set(inner_fold.holdout_dates).isdisjoint(final)
        assert outer_holdout.isdisjoint(final)


def test_summary_uses_total_action_rows_not_unweighted_fold_mean():
    summary = service._summary("candidate", [
        CalibrationCandidateFoldResult(fold_number=1, status="evaluated", action_row_count=1, action_row_threshold_hit_count=1, action_row_threshold_hit_rate=1, mean_realized_excess_return=0.1),
        CalibrationCandidateFoldResult(fold_number=2, status="evaluated", action_row_count=9, action_row_threshold_hit_count=0, action_row_threshold_hit_rate=0, mean_realized_excess_return=0),
    ])

    assert summary.action_row_count == 10
    assert summary.action_row_threshold_hit_count == 1
    assert summary.action_row_threshold_hit_rate == 0.1


def test_summary_uses_not_evaluated_reason_from_not_evaluated_fold_only():
    summary = service._summary(
        "candidate",
        [
            CalibrationCandidateFoldResult(
                fold_number=1,
                status="evaluated",
                status_reason="unrelated evaluated status",
            ),
            CalibrationCandidateFoldResult(
                fold_number=2,
                status="not_evaluated",
                status_reason="model unavailable",
            ),
        ],
    )

    assert summary.status_reason == "model unavailable"
    assert summary.rejection_reason == "model unavailable"


def test_exact_semantic_tie_uses_candidate_id_only_for_determinism():
    ranked = service._rank([
        MethodCandidateSummary(candidate_id="z", status="evaluated", action_row_threshold_hit_rate=.5, mean_realized_excess_return=.1, baseline_relative_mean_net_return=.01),
        MethodCandidateSummary(candidate_id="a", status="evaluated", action_row_threshold_hit_rate=.5, mean_realized_excess_return=.1, baseline_relative_mean_net_return=.01),
    ], outer=False)

    assert [x.candidate_id for x in ranked] == ["a", "z"]
    assert all(x.semantic_tie and x.deterministic_tie_break == "candidate_id" for x in ranked)


def test_outer_stability_requires_two_outer_fold_results():
    ranked = service._rank([
        MethodCandidateSummary(candidate_id="one", status="evaluated", action_row_threshold_hit_rate=.5, mean_realized_excess_return=.1, action_row_stability=None, baseline_relative_mean_net_return=.01),
        MethodCandidateSummary(candidate_id="many", status="evaluated", action_row_threshold_hit_rate=.5, mean_realized_excess_return=.1, action_row_stability=.9, baseline_relative_mean_net_return=.01),
    ], outer=True)

    assert [item.candidate_id for item in ranked] == ["many", "one"]


def test_generic_model_failure_becomes_structured_evaluation_error(monkeypatch):
    sets, specs = service.build_feature_set_manifests()
    manifest = service.build_screening_candidate_manifests(_request(), sets[:1])[0]
    dates = tuple(date(2020, 1, 1) + timedelta(days=index) for index in range(20))
    frame = pd.DataFrame({"date": dates, "symbol": ["AAA"] * 20, "target": [.01] * 20, "target_end_date": dates, specs["baseline"][0].name.upper() + "_5": [1.] * 20})
    fold = build_market_date_folds(dates, splits=1, test_size=.2, purge=1)[0]
    monkeypatch.setattr(service.calibration_service.model_service, "fit_regressor", lambda **_: (_ for _ in ()).throw(ValueError("bad model")))

    with pytest.raises(CalibrationEvaluationError):
        service._evaluate_group([manifest], frame, {"baseline": ("MA_5",)}, [fold], {"regression": 0, "gate": 0})


def test_xgboost_unavailable_is_preserved_without_model_fallback(monkeypatch):
    request = _request().model_copy(update={"model_families": ["xgboost"]})
    feature_sets, _ = service.build_feature_set_manifests()
    manifest = service.build_tuning_candidate_manifests(request, feature_sets[0])[0]
    dates = tuple(date(2020, 1, 1) + timedelta(days=index) for index in range(20))
    frame = pd.DataFrame({"date": dates, "symbol": ["AAA"] * 20, "target": [.01] * 20, "target_end_date": dates, "MA_5": [1.] * 20})
    fold = build_market_date_folds(dates, splits=1, test_size=.2, purge=1)[0]
    monkeypatch.setattr(service.calibration_service.model_service, "fit_regressor", lambda **_: (_ for _ in ()).throw(ModelUnavailableError("xgboost unavailable")))

    result = service._evaluate_group([manifest], frame, {"baseline": ("MA_5",)}, [fold], {"regression": 0, "gate": 0})

    candidate_fold = result.candidate_folds[manifest.candidate_id][0]

    assert candidate_fold.status == "not_evaluated"
    assert "xgboost" in candidate_fold.status_reason.lower()


def test_final_candidate_refit_purges_labels_that_reach_final_holdout(monkeypatch):
    feature_sets, _ = service.build_feature_set_manifests()
    manifest = service.build_tuning_candidate_manifests(_request(), feature_sets[0])[0]
    dates = tuple(date(2020, 1, 1) + timedelta(days=index) for index in range(18))
    final_fold = service.MarketDateFold(
        number=6,
        train_dates=dates[:10],
        purge_dates=dates[10:12],
        holdout_dates=dates[12:15],
    )
    target_end_dates = [item + timedelta(days=1) for item in dates]
    target_end_dates[8] = dates[12]
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAA"] * len(dates),
            "target": [0.2] * len(dates),
            "target_end_date": target_end_dates,
            "MA_5": [1.0] * len(dates),
            "open_to_open_volatility_20": [0.1] * len(dates),
            "open_to_open_volatility_60": [0.1] * len(dates),
            "open_to_open_volatility_252": [0.1] * len(dates),
        }
    )
    captured: dict[str, object] = {}

    class FakeRegressor:
        feature_importances_ = np.array([1.0])

        def predict(self, features):
            return np.ones(len(features))

    class FakeClassifier:
        classes_ = np.array([0, 1])

        def predict_proba(self, features):
            return np.tile([0.1, 0.9], (len(features), 1))

    def fit_regressor(**kwargs):
        captured["X_train"] = kwargs["X_train"].copy()
        captured["y_train"] = kwargs["y_train"].copy()
        return FakeRegressor()

    monkeypatch.setattr(
        service.calibration_service.model_service,
        "fit_regressor",
        fit_regressor,
    )
    monkeypatch.setattr(
        service.calibration_service,
        "_fit_pooled_direction_classifier",
        lambda **_: (FakeClassifier(), None, None),
    )

    artifacts = service._evaluate_final_candidate(
        manifest,
        frame,
        {"baseline": ("MA_5",)},
        final_fold,
        {"regression": 0, "gate": 0},
    )

    assert artifacts.fold_result.status == "evaluated"
    assert len(captured["X_train"]) == 9
    assert 8 not in captured["X_train"].index
    assert set(captured["X_train"].index).isdisjoint({12, 13, 14})


def test_promoted_final_candidate_emits_reloadable_holdout_run(monkeypatch):
    feature_sets, specs_by_id = service.build_feature_set_manifests()
    manifest = service.build_tuning_candidate_manifests(_request(), feature_sets[0])[0]
    feature_names = tuple(feature_sets[0].feature_names)
    dates = tuple(date(2020, 1, 1) + timedelta(days=index) for index in range(30))
    fold = service.MarketDateFold(
        number=6,
        train_dates=dates[:20],
        purge_dates=dates[20:25],
        holdout_dates=dates[25:],
    )
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAA"] * len(dates),
            "target": [0.02] * len(dates),
            "target_end_date": [item + timedelta(days=1) for item in dates],
            "open": [100.0 + index for index in range(len(dates))],
            "high": [101.0 + index for index in range(len(dates))],
            "low": [99.0 + index for index in range(len(dates))],
            "close": [100.5 + index for index in range(len(dates))],
            "volume": [1000.0] * len(dates),
            **{feature: [1.0] * len(dates) for feature in feature_names},
            **{
                f"open_to_open_volatility_{lookback}": [0.1] * len(dates)
                for lookback in (20, 60, 252)
            },
        }
    )

    class FakeRegressor:
        feature_importances_ = np.ones(len(feature_names))

        def predict(self, features):
            return np.ones(len(features))

    class FakeClassifier:
        classes_ = np.array([0, 1])

        def predict_proba(self, features):
            probabilities = np.tile([0.1, 0.9], (len(features), 1))
            probabilities[1::2] = [0.9, 0.1]
            return probabilities

    monkeypatch.setattr(
        service.calibration_service.model_service,
        "fit_regressor",
        lambda **_: FakeRegressor(),
    )
    monkeypatch.setattr(
        service.calibration_service,
        "_fit_pooled_direction_classifier",
        lambda **_: (FakeClassifier(), None, None),
    )
    captured_backtest: dict[str, pd.DataFrame] = {}

    def fake_backtest(**kwargs):
        captured_backtest["weights"] = kwargs["weights"].copy()
        return (
            {
                "total_return": 0.1,
                "sharpe": 0.2,
                "max_drawdown": -0.05,
                "turnover": 0.4,
                "max_position_weight": 1.0,
            },
            [
                {"date": item.date(), "equity": 1.0}
                for item in kwargs["weights"].index
            ],
        )

    monkeypatch.setattr(
        service.backtest_service,
        "run_backtest_from_weights",
        fake_backtest,
    )
    started: list[dict] = []
    completed: list[dict] = []
    monkeypatch.setattr(service, "record_started", lambda **kwargs: started.append(kwargs))
    monkeypatch.setattr(
        service,
        "record_success",
        lambda **kwargs: completed.append(kwargs),
    )
    artifacts = service._evaluate_final_candidate(
        manifest,
        frame,
        {"baseline": feature_names},
        fold,
        {"regression": 0, "gate": 0},
    )

    run_id = service._promote_final_candidate(
        _request(),
        matrix_id="matrix_promote",
        request_id="request_promote",
        shortlisted_candidate_id=manifest.candidate_id,
        manifest=manifest,
        artifacts=artifacts,
        final_boundary=service._boundary(fold, frame),
        final_inner_selected_candidate_id=manifest.candidate_id,
        specs_by_id=specs_by_id,
    )

    assert run_id.startswith("research_run_")
    assert len(started) == 1
    assert len(completed) == 1
    promoted_response = completed[0]["response"]
    assert promoted_response.artifact_completeness == "complete"
    assert promoted_response.signals
    assert all(
        item.signal_kind == "holdout_evaluation" for item in promoted_response.signals
    )
    expected_index = pd.DatetimeIndex(pd.to_datetime(fold.holdout_dates))
    assert captured_backtest["weights"].index.equals(expected_index)
    assert captured_backtest["weights"].columns.tolist() == ["AAA"]
    assert captured_backtest["weights"].iloc[1, 0] == 0.0
    assert promoted_response.effective_strategy.threshold_mode == "dynamic"
    assert promoted_response.effective_strategy.threshold is None
    assert promoted_response.effective_strategy.dynamic_threshold_policy is not None
    assert promoted_response.config_sources.strategy.threshold == "derived_policy"
    assert completed[0]["request"].strategy.threshold_mode == "dynamic"
    assert completed[0]["request"].strategy.threshold is None
    assert completed[0]["request_payload_extra"]["matrix_id"] == "matrix_promote"


def _synthetic_method_selection_datasets():
    feature_sets, specs_by_id = service.build_feature_set_manifests()
    feature_names_by_set = {
        item.feature_set_id: tuple(item.feature_names) for item in feature_sets
    }
    selection_dates = tuple(
        date(2018, 1, 1) + timedelta(days=index) for index in range(300)
    )
    final_dates = tuple(
        date(2018, 1, 1) + timedelta(days=index) for index in range(300, 552)
    )
    all_dates = selection_dates + final_dates
    frame = pd.DataFrame(
        {
            "date": all_dates,
            "symbol": ["AAA"] * len(all_dates),
            "target": [0.01] * len(all_dates),
            "target_end_date": [item + timedelta(days=1) for item in all_dates],
            "open": [1.0] * len(all_dates),
            "high": [1.0] * len(all_dates),
            "low": [1.0] * len(all_dates),
            "close": [1.0] * len(all_dates),
            "volume": [1.0] * len(all_dates),
            **{
                feature: [1.0] * len(all_dates)
                for feature in feature_names_by_set["full"]
            },
            **{
                f"open_to_open_volatility_{lookback}": [0.1] * len(all_dates)
                for lookback in (20, 60, 252)
            },
        }
    )
    # This row is inside the final refit train axis but its label settles on
    # the first Final Holdout date, so the boundary audit must count it.
    frame.loc[294, "target_end_date"] = final_dates[0]
    selection_frame = frame.loc[frame["date"].isin(selection_dates)].reset_index(
        drop=True
    )
    full_frame = frame.reset_index(drop=True)
    selection_dataset = PooledModelReadyDataset(
        frame=selection_frame,
        feature_names=feature_names_by_set["full"],
        exclusions=(),
        market_dates=selection_dates,
    )
    full_dataset = PooledModelReadyDataset(
        frame=full_frame,
        feature_names=feature_names_by_set["full"],
        exclusions=(),
        market_dates=all_dates,
    )
    return (
        feature_sets,
        specs_by_id,
        feature_names_by_set,
        selection_dataset,
        full_dataset,
        selection_dates,
        final_dates,
    )


def test_final_inner_selection_is_pre_final_and_final_evaluation_runs_once(monkeypatch):
    (
        feature_sets,
        specs_by_id,
        feature_names_by_set,
        selection_dataset,
        full_dataset,
        selection_dates,
        final_dates,
    ) = _synthetic_method_selection_datasets()
    shortlist_manifest = service.build_tuning_candidate_manifests(
        _request(), feature_sets[0]
    )[0]
    shortlist_summary = MethodCandidateSummary(
        candidate_id=shortlist_manifest.candidate_id,
        status="evaluated",
        action_row_count=1,
        action_row_threshold_hit_count=1,
        action_row_threshold_hit_rate=1.0,
    )
    selection_calls: list[tuple[pd.DataFrame, list]] = []
    final_calls: list[tuple[pd.DataFrame, service.MarketDateFold]] = []

    def fake_evaluate(manifests, frame, _names, folds, _counts):
        selection_calls.append((frame, folds))
        return service._GroupEvaluation(
            {
                manifest.candidate_id: [
                    CalibrationCandidateFoldResult(
                        fold_number=fold.number,
                        status="evaluated",
                        action_row_count=1,
                        action_row_threshold_hit_count=1,
                        action_row_threshold_hit_rate=1.0,
                        mean_realized_excess_return=0.01,
                        baseline_relative_mean_net_return=0.001,
                    )
                    for fold in folds
                ]
                for manifest in manifests
            },
            {
                "extra_trees": service._ModelExecutionEvidence(
                    evaluated_group_fold_count=len(folds)
                )
            },
        )

    def fake_final(manifest, frame, _names, fold, _counts):
        final_calls.append((frame, fold))
        return service._FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=None,
            model=object(),
            scores=np.array([1.0]),
            probabilities=np.array([0.9]),
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="evaluated",
                action_row_count=1,
                action_row_threshold_hit_count=1,
                action_row_threshold_hit_rate=1.0,
                mean_realized_excess_return=0.01,
            ),
        )

    monkeypatch.setattr(service, "_evaluate_group", fake_evaluate)
    monkeypatch.setattr(service, "_evaluate_final_candidate", fake_final)
    monkeypatch.setattr(
        service,
        "_promote_final_candidate",
        lambda *args, **kwargs: "run_promoted_1",
    )

    result = service._build_final_holdout_result(
        _request(),
        matrix_id="matrix_1",
        request_id="request_1",
        shortlist_summary=shortlist_summary,
        feature_sets=feature_sets,
        specs_by_id=specs_by_id,
        feature_names_by_set=feature_names_by_set,
        selection_dataset=selection_dataset,
        full_dataset=full_dataset,
        selection_dates=selection_dates,
        final_holdout_dates=final_dates,
        fit_counts=defaultdict(int),
        phase_b_by_id={shortlist_manifest.candidate_id: shortlist_manifest},
        model_execution={},
    )

    assert result.status == "promoted"
    assert result.promoted_research_run_id == "run_promoted_1"
    assert len(selection_calls) == 1
    assert selection_calls[0][0] is selection_dataset.frame
    assert selection_calls[0][0]["date"].max() < final_dates[0]
    assert len(final_calls) == 1
    assert final_calls[0][0] is full_dataset.frame
    assert final_calls[0][1].holdout_dates == final_dates
    assert result.final_holdout_boundary.holdout_market_date_count == 252
    assert result.final_holdout_boundary.target_purge_row_count >= 1
    assert result.final_candidate_manifest is not None
    assert result.final_candidate_manifest.horizon_days == 5


def test_load_method_selection_datasets_preserves_selection_and_full_axes(monkeypatch):
    feature_sets, specs_by_id = service.build_feature_set_manifests()
    feature_names = {
        feature_set_id: tuple(item.feature_names)
        for feature_set_id, item in ((item.feature_set_id, item) for item in feature_sets)
    }
    dates = tuple(date(2024, 1, 1) + timedelta(days=index) for index in range(500))
    raw = pd.DataFrame({"date": dates, "symbol": ["AAA"] * len(dates), "open": [1.] * len(dates), "high": [1.] * len(dates), "low": [1.] * len(dates), "close": [1.] * len(dates), "volume": [1.] * len(dates)})
    dataset = PooledModelReadyDataset(frame=pd.DataFrame({"date": dates[:-252], "symbol": ["AAA"] * len(dates[:-252])}), feature_names=feature_names["full"], exclusions=(), market_dates=dates[:-252])
    captured_calls = []
    monkeypatch.setattr(service.calibration_service, "_load_market_frame", lambda *_: (raw, dates))

    def fake_build_dataset(*args, **kwargs):
        captured_calls.append(kwargs)
        return dataset

    monkeypatch.setattr(service, "build_pooled_model_ready_dataset", fake_build_dataset)

    request = _request().model_copy(
        update={
            "date_range": DateRange(start=dates[0], end=date(2024, 12, 31)),
        }
    )
    datasets = service._load_method_selection_datasets(
        request, specs_by_id["full"], feature_names
    )

    requested_dates = tuple(item for item in dates if item <= request.date_range.end)
    selection_dates = requested_dates[:-252]
    assert datasets.selection_dates == selection_dates
    assert datasets.final_holdout_dates == requested_dates[-252:]
    assert datasets.final_holdout_maturity_date == dates[366 + request.horizon_days - 1]
    assert datasets.final_holdout_maturity_buffer_market_date_count == len(dates) - 366
    assert [call["market_dates"] for call in captured_calls] == [selection_dates, dates]
    assert all(call["counterfactual_feature_sets"] == feature_names for call in captured_calls)
    assert all(call["complete_case_extra_columns"] == (
        "open_to_open_volatility_20", "open_to_open_volatility_60", "open_to_open_volatility_252"
    ) for call in captured_calls)


def test_method_selection_rejects_without_post_range_maturity_buffer(monkeypatch):
    dates = tuple(
        date(2020, 1, 1) + timedelta(days=index) for index in range(500)
    )
    request = _request().model_copy(
        update={"date_range": DateRange(start=dates[0], end=dates[-1])}
    )
    raw = pd.DataFrame({"date": [dates[-1]], "symbol": ["AAA"]})
    persisted = []
    monkeypatch.setattr(
        service.calibration_service,
        "_load_market_frame",
        lambda *_: (raw, dates),
    )
    monkeypatch.setattr(
        service,
        "persist_method_selection_batch",
        lambda *args, **kwargs: persisted.append((args, kwargs)),
    )

    with pytest.raises(InsufficientDataError, match="mature"):
        service._create_method_selection_matrix(
            request,
            request_id="request_without_buffer",
            matrix_id="matrix_without_buffer",
        )

    assert persisted == []


def test_final_promotion_failure_is_retained_without_stopping_lineage(monkeypatch):
    (
        feature_sets,
        specs_by_id,
        feature_names_by_set,
        selection_dataset,
        full_dataset,
        selection_dates,
        final_dates,
    ) = _synthetic_method_selection_datasets()
    manifest = service.build_tuning_candidate_manifests(
        _request(), feature_sets[0]
    )[0]
    final_inner_selection = service._FinalInnerSelection(
        manifests=(manifest,),
        folds=(),
        summaries=(
            MethodCandidateSummary(
                candidate_id=manifest.candidate_id,
                status="evaluated",
                action_row_count=1,
                action_row_threshold_hit_count=1,
                action_row_threshold_hit_rate=1.0,
            ),
        ),
        selected_manifest=manifest,
    )

    monkeypatch.setattr(
        service,
        "_evaluate_final_candidate",
        lambda manifest, frame, names, fold, counts: service._FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=None,
            model=object(),
            scores=np.array([1.0]),
            probabilities=np.array([0.9]),
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="evaluated",
                action_row_count=1,
                action_row_threshold_hit_count=1,
                action_row_threshold_hit_rate=1.0,
            ),
        ),
    )
    monkeypatch.setattr(
        service,
        "_prepare_promoted_final_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CalibrationEvaluationError("artifact assembly failed")
        ),
    )

    prepared_runs: list[service._PreparedPromotedRun] = []
    result = service._build_final_holdout_result(
        _request(),
        matrix_id="matrix_failure",
        request_id="request_failure",
        shortlist_summary=MethodCandidateSummary(
            candidate_id=manifest.candidate_id,
            status="evaluated",
            action_row_count=1,
            action_row_threshold_hit_count=1,
            action_row_threshold_hit_rate=1.0,
        ),
        feature_sets=feature_sets,
        specs_by_id=specs_by_id,
        feature_names_by_set=feature_names_by_set,
        selection_dataset=selection_dataset,
        full_dataset=full_dataset,
        selection_dates=selection_dates,
        final_holdout_dates=final_dates,
        fit_counts=defaultdict(int),
        phase_b_by_id={},
        model_execution={},
        final_inner_selection=final_inner_selection,
        prepared_runs=prepared_runs,
    )

    assert result.status == "not_evaluated"
    assert "artifact assembly failed" in (result.status_reason or "")
    assert prepared_runs == []


def test_final_inner_selection_failure_keeps_typed_reason(monkeypatch):
    (
        feature_sets,
        specs_by_id,
        feature_names_by_set,
        selection_dataset,
        full_dataset,
        selection_dates,
        final_dates,
    ) = _synthetic_method_selection_datasets()
    manifest = service.build_tuning_candidate_manifests(
        _request(), feature_sets[0]
    )[0]
    monkeypatch.setattr(
        service,
        "_build_final_inner_selection",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError()),
    )

    result = service._build_final_holdout_result(
        _request(),
        matrix_id="matrix_inner_failure",
        request_id="request_inner_failure",
        shortlist_summary=MethodCandidateSummary(
            candidate_id=manifest.candidate_id,
            status="evaluated",
        ),
        feature_sets=feature_sets,
        specs_by_id=specs_by_id,
        feature_names_by_set=feature_names_by_set,
        selection_dataset=selection_dataset,
        full_dataset=full_dataset,
        selection_dates=selection_dates,
        final_holdout_dates=final_dates,
        fit_counts=defaultdict(int),
        phase_b_by_id={},
        model_execution={},
        final_inner_selection=None,
        prepared_runs=[],
    )

    assert result.status == "not_evaluated"
    assert result.status_reason == (
        "Final inner selection could not be formed: RuntimeError"
    )


def test_method_selection_batch_rolls_back_promoted_runs_on_matrix_failure(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            MethodSelectionMatrix.__table__,
            ResearchRun.__table__,
            ResearchRunLiquidityCoverage.__table__,
        ],
    )
    testing_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(method_selection_repository, "SessionLocal", testing_session_local)
    monkeypatch.setattr(
        method_selection_repository,
        "persist_method_selection_matrix",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("matrix write failed")
        ),
    )
    run_payload = {
        "run_id": "atomic_run",
        "request_id": "atomic_request",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["AAA"],
        "strategy_type": "research_v1",
        "runtime_mode": "runtime_compatibility_mode",
        "effective_strategy": {"threshold": 0.1, "top_n": 1},
        "request_payload": {
            "market": "TW",
            "symbols": ["AAA"],
            "strategy": {
                "type": "research_v1",
                "threshold": 0.1,
                "top_n": 1,
            },
        },
        "metrics": {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "turnover": 0.0,
            "max_position_weight": 0.0,
        },
        "equity_curve": [],
        "signals": [],
        "warnings": [],
        "baselines": {},
    }

    with pytest.raises(DataAccessError, match="batch"):
        method_selection_repository.persist_method_selection_batch(
            {"matrix_id": "atomic_matrix", "request_id": "atomic_request", "status": "succeeded"},
            [run_payload],
        )

    with testing_session_local() as session:
        assert session.get(ResearchRun, "atomic_run") is None
        assert session.get(MethodSelectionMatrix, "atomic_matrix") is None


def test_create_matrix_connects_phase_a_phase_b_and_evidence(monkeypatch):
    feature_sets, _specs_by_id = service.build_feature_set_manifests()
    dates = tuple(date(2018, 1, 1) + timedelta(days=index) for index in range(1000))
    full_features = tuple(
        feature_sets[
            [item.feature_set_id for item in feature_sets].index("full")
        ].feature_names
    )
    selection_dates = dates[:-252]
    model_ready_dates = selection_dates[253:]
    frame = pd.DataFrame(
        {
            "date": model_ready_dates,
            "symbol": ["AAA"] * len(model_ready_dates),
            "target": [.01] * len(model_ready_dates),
            "target_end_date": [item + timedelta(days=1) for item in model_ready_dates],
            **{name: [1.] * len(model_ready_dates) for name in full_features},
            **{
                f"open_to_open_volatility_{lookback}": [.1] * len(model_ready_dates)
                for lookback in (20, 60, 252)
            },
        }
    )
    dataset = PooledModelReadyDataset(
        frame=frame,
        feature_names=full_features,
        exclusions=(),
        market_dates=selection_dates,
        deduplicated_row_count=7,
        counterfactual_complete_case_row_counts={
            item.feature_set_id: len(frame) + 3 for item in feature_sets
        },
    )
    calls = []

    def fake_evaluate(manifests, _frame, _names, folds, _counts):
        calls.append((manifests, folds))
        results = {
            manifest.candidate_id: [CalibrationCandidateFoldResult(fold_number=fold.number, status="evaluated", action_row_count=1, action_row_threshold_hit_count=1, action_row_threshold_hit_rate=1, mean_realized_excess_return=.01, baseline_relative_mean_net_return=.001) for fold in folds]
            for manifest in manifests
        }
        execution = {manifest.model_type: service._ModelExecutionEvidence(evaluated_group_fold_count=len(folds)) for manifest in manifests}
        return service._GroupEvaluation(results, execution)

    persisted = []
    monkeypatch.setattr(
        service,
        "_load_method_selection_datasets",
        lambda *_: service._MethodSelectionDatasets(
            selection=dataset,
            full=dataset,
            selection_dates=selection_dates,
            final_holdout_dates=dates[-252:],
        ),
    )
    monkeypatch.setattr(service, "_evaluate_group", fake_evaluate)
    monkeypatch.setattr(
        service,
        "persist_method_selection_batch",
        lambda matrix_payload, run_payloads: persisted.append(
            (matrix_payload, run_payloads)
        )
        or matrix_payload,
    )
    monkeypatch.setattr(service.calibration_service, "_peak_rss_bytes", lambda: 123)
    monkeypatch.setattr(
        service,
        "_evaluate_final_candidate",
        lambda manifest, frame, names, fold, counts: service._FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=None,
            model=None,
            scores=None,
            probabilities=None,
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="not_evaluated",
                status_reason="fixture final evaluation unavailable",
            ),
        ),
    )

    response = service._create_method_selection_matrix(_request(), request_id="request", matrix_id="matrix")

    assert len(response.outer_folds) == 5
    assert all(record.phase_a_selected_candidate_id for record in response.outer_folds)
    assert all(
        boundary.train_row_count > 0
        for record in response.outer_folds
        for boundary in record.inner_folds
    )
    phase_b_calls = [
        manifests
        for manifests, folds in calls
        if len(folds) == 3
        and manifests[0].phase == "parameter_search"
        and len({manifest.feature_set_id for manifest in manifests}) == 1
    ]
    assert len(phase_b_calls) == 5
    assert all(
        {manifest.feature_set_id for manifest in manifests} == {"baseline"}
        for manifests in phase_b_calls
    )
    assert response.final_holdout_market_dates == list(dates[-252:])
    assert len(response.final_inner_candidate_manifests) == 18 * 3 * 3 * 3 * 3
    assert all(
        set(boundary_dates(record.outer_fold)).isdisjoint(dates[-252:])
        for record in response.outer_folds
    )
    assert response.resource_evidence.peak_rss_bytes == 123
    assert response.resource_evidence.deduplicated_market_date_row_count == 7
    assert response.comparability_evidence.common_policy_rows_lost_by_feature_set["baseline"] == 3
    assert persisted[0][0]["matrix_id"] == "matrix"
    assert persisted[0][1] == []
    assert response.comparability_evidence.selection_market_date_count == len(selection_dates)
    assert response.comparability_evidence.common_market_date_count == len(model_ready_dates)


def test_create_matrix_retains_three_lineages_and_duplicate_configuration_evidence(
    monkeypatch,
):
    feature_sets, _ = service.build_feature_set_manifests()
    dates = tuple(date(2018, 1, 1) + timedelta(days=index) for index in range(1000))
    feature_names = tuple(feature_sets[-1].feature_names)
    selection_dates = dates[:-252]
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAA"] * len(dates),
            "target": [0.01] * len(dates),
            "target_end_date": [item + timedelta(days=1) for item in dates],
            **{name: [1.0] * len(dates) for name in feature_names},
            **{
                f"open_to_open_volatility_{lookback}": [0.1] * len(dates)
                for lookback in (20, 60, 252)
            },
        }
    )
    dataset = PooledModelReadyDataset(
        frame=frame,
        feature_names=feature_names,
        exclusions=(),
        market_dates=dates,
    )
    phase_b_calls = 0

    def fake_evaluate(manifests, _frame, _names, folds, _counts):
        nonlocal phase_b_calls
        is_phase_b = manifests and manifests[0].phase == "parameter_search"
        is_outer_selection = is_phase_b and len(folds) == 3 and phase_b_calls < 5
        if is_outer_selection:
            phase_b_calls += 1
        winner_index = (phase_b_calls - 1) % 3 if is_outer_selection else 0
        results = {}
        for index, manifest in enumerate(manifests):
            score = 1.0 if index == winner_index else 0.1
            results[manifest.candidate_id] = [
                CalibrationCandidateFoldResult(
                    fold_number=fold.number,
                    status="evaluated",
                    action_row_count=1,
                    action_row_threshold_hit_count=1,
                    action_row_threshold_hit_rate=score,
                    mean_realized_excess_return=score,
                    baseline_relative_mean_net_return=score,
                )
                for fold in folds
            ]
        execution = {
            manifest.model_type: service._ModelExecutionEvidence(
                evaluated_group_fold_count=len(folds)
            )
            for manifest in manifests
        }
        return service._GroupEvaluation(results, execution)

    def fake_final(manifest, _frame, _names, fold, _counts):
        return service._FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=None,
            model=object(),
            scores=np.array([1.0]),
            probabilities=np.array([0.9]),
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="evaluated",
                action_row_count=1,
                action_row_threshold_hit_count=1,
                action_row_threshold_hit_rate=1.0,
            ),
        )

    def fake_prepare(request, *, shortlisted_candidate_id, manifest, **kwargs):
        run_id = f"run_{shortlisted_candidate_id}"
        return service._PreparedPromotedRun(
            run_id=run_id,
            request=None,
            runtime_context={},
            response=None,
            registry_payload={
                "request_payload": {
                    "method_selection": {
                        "shortlisted_candidate_id": shortlisted_candidate_id,
                    }
                }
            },
        )

    persisted = []
    monkeypatch.setattr(
        service,
        "_load_method_selection_datasets",
        lambda *_: service._MethodSelectionDatasets(
            selection=dataset,
            full=dataset,
            selection_dates=selection_dates,
            final_holdout_dates=dates[-252:],
        ),
    )
    monkeypatch.setattr(service, "_evaluate_group", fake_evaluate)
    monkeypatch.setattr(service, "_evaluate_final_candidate", fake_final)
    monkeypatch.setattr(service, "_prepare_promoted_final_candidate", fake_prepare)
    monkeypatch.setattr(
        service,
        "persist_method_selection_batch",
        lambda matrix_payload, run_payloads: persisted.append(
            (matrix_payload, run_payloads)
        )
        or matrix_payload,
    )
    monkeypatch.setattr(service.calibration_service, "_peak_rss_bytes", lambda: 0)

    response = service._create_method_selection_matrix(
        _request(), request_id="request_duplicate", matrix_id="matrix_duplicate"
    )

    assert phase_b_calls == 5
    assert len(response.shortlist) == 3
    assert len(response.final_holdout_results) == 3
    assert len(response.promoted_research_run_ids) == 3
    assert len(set(response.promoted_research_run_ids)) == 3
    assert len({item.final_candidate_id for item in response.final_holdout_results}) == 1
    assert all(item.same_final_configuration for item in response.final_holdout_results)
    group_ids = {
        item.final_configuration_group_id for item in response.final_holdout_results
    }
    assert len(group_ids) == 1
    assert all(
        set(item.duplicate_configuration_run_ids)
        == set(response.promoted_research_run_ids)
        - {item.promoted_research_run_id}
        for item in response.final_holdout_results
    )
    assert response.resource_evidence.final_inner_execution_count == 1
    assert response.resource_evidence.final_inner_reuse_count == 2
    assert response.resource_evidence.final_holdout_execution_count == 1
    assert response.resource_evidence.final_holdout_reuse_count == 2
    assert len(persisted) == 1
    assert len(persisted[0][1]) == 3


def test_create_promotion_and_reload_use_one_atomic_registry_path(monkeypatch):
    request = _request()
    feature_set = MethodSelectionFeatureSetManifest(
        feature_set_id="baseline",
        included_feature_families=[],
        baseline_feature_names=["ma"],
        feature_names=["MA_5"],
    )
    manifest = service._manifest(
        "parameter_search",
        feature_set,
        request,
        "extra_trees",
        "balanced",
        20,
        0.5,
        1,
    )
    dates = tuple(date(2018, 1, 1) + timedelta(days=index) for index in range(700))
    selection_dates = dates[:-252]
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAA"] * len(dates),
            "target": [0.01] * len(dates),
            "target_end_date": [item + timedelta(days=1) for item in dates],
            "MA_5": [1.0] * len(dates),
            **{
                f"open_to_open_volatility_{lookback}": [0.1] * len(dates)
                for lookback in (20, 60, 252)
            },
        }
    )
    selection_dataset = PooledModelReadyDataset(
        frame=frame.loc[frame["date"].isin(selection_dates)].reset_index(drop=True),
        feature_names=("MA_5",),
        exclusions=(),
        market_dates=selection_dates,
    )
    full_dataset = PooledModelReadyDataset(
        frame=frame,
        feature_names=("MA_5",),
        exclusions=(),
        market_dates=dates,
    )

    monkeypatch.setattr(
        service,
        "build_feature_set_manifests",
        lambda: ([feature_set], {"baseline": []}),
    )
    monkeypatch.setattr(
        service,
        "build_tuning_candidate_manifests",
        lambda *_: [manifest],
    )
    monkeypatch.setattr(
        service,
        "_load_method_selection_datasets",
        lambda *_: service._MethodSelectionDatasets(
            selection=selection_dataset,
            full=full_dataset,
            selection_dates=selection_dates,
            final_holdout_dates=dates[-252:],
            final_holdout_maturity_date=dates[-1] + timedelta(days=5),
            final_holdout_maturity_buffer_market_date_count=5,
        ),
    )
    monkeypatch.setattr(
        service,
        "_evaluate_group",
        lambda manifests, _frame, _names, folds, _counts: service._GroupEvaluation(
            {
                item.candidate_id: [
                    CalibrationCandidateFoldResult(
                        fold_number=fold.number,
                        status="evaluated",
                        action_row_count=1,
                        action_row_threshold_hit_count=1,
                        action_row_threshold_hit_rate=1.0,
                        mean_realized_excess_return=0.01,
                        baseline_relative_mean_net_return=0.001,
                    )
                    for fold in folds
                ]
                for item in manifests
            },
            {
                item.model_type: service._ModelExecutionEvidence(
                    evaluated_group_fold_count=len(folds)
                )
                for item in manifests
            },
        ),
    )
    monkeypatch.setattr(
        service,
        "_evaluate_final_candidate",
        lambda manifest, _frame, _names, fold, _counts: service._FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=None,
            model=object(),
            scores=np.array([1.0]),
            probabilities=np.array([0.9]),
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="evaluated",
                action_row_count=1,
                action_row_threshold_hit_count=1,
                action_row_threshold_hit_rate=1.0,
            ),
        ),
    )

    def fake_prepare(request, *, matrix_id, request_id, shortlisted_candidate_id, **_):
        run_id = "e2e_promoted_run"
        request_payload = {
            "runtime_mode": "runtime_compatibility_mode",
            "market": "TW",
            "symbols": ["AAA"],
            "date_range": request.date_range.model_dump(mode="json"),
            "return_target": "open_to_open",
            "horizon_days": request.horizon_days,
            "features": [{"name": "ma", "window": 5, "source": "close", "shift": 1}],
            "model": {"type": "extra_trees", "params": {}},
            "strategy": {
                "type": "research_v1",
                "threshold": 0.1,
                "top_n": 1,
                "threshold_mode": "static",
                "dynamic_threshold_policy": None,
                "allow_proactive_sells": True,
            },
            "execution": {"fees": 0.002, "slippage": 0.001},
            "validation": None,
            "baselines": [],
            "method_selection": {
                "matrix_id": matrix_id,
                "shortlisted_candidate_id": shortlisted_candidate_id,
            },
        }
        registry_payload = {
            "run_id": run_id,
            "request_id": f"{request_id}:promoted:{run_id}",
            "status": "succeeded",
            "feature_registry_version": "registry",
            "market": "TW",
            "symbols": ["AAA"],
            "strategy_type": "research_v1",
            "runtime_mode": "runtime_compatibility_mode",
            "effective_strategy": {"threshold": 0.1, "top_n": 1},
            "allow_proactive_sells": True,
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
            "request_payload": request_payload,
            "metrics": {
                "total_return": 0.1,
                "sharpe": 0.2,
                "max_drawdown": -0.05,
                "turnover": 0.1,
                "max_position_weight": 1.0,
            },
            "equity_curve": [{"date": dates[-1], "equity": 1.1}],
            "signals": [
                {
                    "date": dates[-1],
                    "symbol": "AAA",
                    "score": 1.0,
                    "position": 1.0,
                    "signal_kind": "holdout_evaluation",
                }
            ],
            "model_diagnostics": {
                "task": "regression",
                "sample_count": 1,
                "rmse": 0.1,
                "mae": 0.1,
            },
            "baselines": {},
            "warnings": [],
            "comparison_eligibility": "research_only_comparable",
            "execution_route": "research_only",
        }
        return service._PreparedPromotedRun(
            run_id=run_id,
            request=None,
            runtime_context={},
            response=None,
            registry_payload=registry_payload,
        )

    monkeypatch.setattr(service, "_prepare_promoted_final_candidate", fake_prepare)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            MethodSelectionMatrix.__table__,
            ResearchRun.__table__,
            ResearchRunLiquidityCoverage.__table__,
        ],
    )
    testing_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(method_selection_repository, "SessionLocal", testing_session_local)
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)
    monkeypatch.setattr(service.calibration_service, "_peak_rss_bytes", lambda: 0)

    response = service._create_method_selection_matrix(
        request, request_id="e2e_request", matrix_id="e2e_matrix"
    )
    loaded_matrix = service.get_method_selection_matrix("e2e_matrix")
    loaded_run = research_run_projection.get_research_run_record("e2e_promoted_run")

    assert response.promoted_research_run_ids == ["e2e_promoted_run"]
    assert loaded_matrix.matrix_id == "e2e_matrix"
    assert loaded_matrix.final_holdout_results[0].status == "promoted"
    assert loaded_run["artifact_completeness"] == "complete"
    assert loaded_run["metrics"]["total_return"] == pytest.approx(0.1)


def boundary_dates(boundary):
    if boundary.train_date_start is None or boundary.holdout_date_end is None:
        return ()
    return tuple(
        boundary.train_date_start + timedelta(days=index)
        for index in range(
            (boundary.holdout_date_end - boundary.train_date_start).days + 1
        )
    )


def test_method_selection_availability_does_not_reuse_calibration_fold_count():
    manifests, _ = service.build_feature_set_manifests()
    candidate = service.build_screening_candidate_manifests(_request(), manifests[:1])

    availability = service._availability(
        candidate,
        {"extra_trees": service._ModelExecutionEvidence(evaluated_group_fold_count=54)},
    )

    payload = availability[0].model_dump()
    assert payload["evaluated_group_fold_count"] == 54
    assert "evaluated_fold_count" not in payload


def test_method_selection_api_contract_includes_caveat_and_evidence(monkeypatch):
    response = MethodSelectionMatrixResponse(
        matrix_id="matrix_1", request_id="req_1", request=_request(),
        feature_registry_version="registry", dataset={"requested_symbol_count": 2},
        final_holdout_policy_version="policy", final_holdout_market_dates=[],
        fold_policy_version="fold", policy_version="policy",
        feature_ablation_policy_version="ablation", ranking_policy_version="rank",
        screening_policy_version="screening", outer_stability_policy_version="stability",
        feature_sets=[], phase_a_candidate_manifests=[],
        phase_b_candidate_manifests=[], outer_folds=[], resource_evidence={"wall_clock_seconds": 0, "cpu_seconds": 0},
        comparability_evidence={"policy_version": "common"}, created_at="2024-01-01T00:00:00Z",
    )
    monkeypatch.setattr(research_api, "create_method_selection_matrix", lambda *args, **kwargs: response)
    monkeypatch.setattr(research_api, "get_method_selection_matrix", lambda *_: response)

    assert client.post("/api/v1/research/method-selection-matrices", json=_request().model_dump(mode="json")).status_code == 200
    assert client.get("/api/v1/research/method-selection-matrices/matrix_1").json()["resource_evidence"]


def _matrix_response_with_final_results(
    *,
    matrix_maturity: date | None,
    result_maturities: list[date | None],
    result_run_ids: list[str],
    promoted_run_ids: list[str],
) -> MethodSelectionMatrixResponse:
    feature_sets, _ = service.build_feature_set_manifests()
    manifest = service.build_tuning_candidate_manifests(
        _request(), feature_sets[0]
    )[0]
    final_dates = [date(2024, 1, 2)]
    boundary = MethodSelectionFoldBoundary(
        number=6,
        train_market_date_count=1,
        holdout_market_date_count=1,
    )
    final_evaluation = CalibrationCandidateFoldResult(
        fold_number=6,
        status="evaluated",
    )
    shortlist_ids = [f"shortlist_{index}" for index in range(len(result_run_ids))]
    return MethodSelectionMatrixResponse(
        matrix_id="matrix_contract",
        request_id="request_contract",
        request=_request(),
        feature_registry_version="registry",
        dataset={"requested_symbol_count": 2},
        final_holdout_policy_version="final_holdout_policy",
        final_holdout_market_dates=final_dates,
        fold_policy_version="fold",
        policy_version="policy",
        feature_ablation_policy_version="ablation",
        ranking_policy_version="rank",
        screening_policy_version="screening",
        outer_stability_policy_version="stability",
        feature_sets=[],
        phase_a_candidate_manifests=[],
        phase_b_candidate_manifests=[manifest],
        outer_folds=[],
        shortlist=[
            {"candidate_id": candidate_id, "status": "evaluated"}
            for candidate_id in shortlist_ids
        ],
        final_holdout_results=[
            {
                "shortlisted_candidate_id": candidate_id,
                "final_candidate_id": manifest.candidate_id,
                "final_candidate_manifest": manifest,
                "final_holdout_policy_version": "final_holdout_policy",
                "final_holdout_market_dates": final_dates,
                "final_holdout_boundary": boundary,
                "final_holdout_maturity_date": result_maturity,
                "final_holdout_evaluation": final_evaluation,
                "status": "promoted",
                "promoted_research_run_id": run_id,
            }
            for candidate_id, result_maturity, run_id in zip(
                shortlist_ids,
                result_maturities,
                result_run_ids,
                strict=True,
            )
        ],
        final_holdout_maturity_date=matrix_maturity,
        promoted_research_run_ids=promoted_run_ids,
        resource_evidence={"wall_clock_seconds": 0, "cpu_seconds": 0},
        comparability_evidence={"policy_version": "common"},
        created_at="2024-01-01T00:00:00Z",
    )


def test_matrix_rejects_duplicate_promoted_result_run_ids():
    with pytest.raises(
        ValueError,
        match="each promoted final result must reference a unique Research Run",
    ):
        _matrix_response_with_final_results(
            matrix_maturity=None,
            result_maturities=[None, None],
            result_run_ids=["run_duplicate", "run_duplicate"],
            promoted_run_ids=["run_duplicate"],
        )


@pytest.mark.parametrize(
    ("matrix_maturity", "result_maturity"),
    [
        (None, date(2024, 1, 10)),
        (date(2024, 1, 10), None),
    ],
)
def test_matrix_rejects_one_sided_final_holdout_maturity_date(
    matrix_maturity,
    result_maturity,
):
    with pytest.raises(
        ValueError,
        match="final results must retain the Matrix Holdout maturity date",
    ):
        _matrix_response_with_final_results(
            matrix_maturity=matrix_maturity,
            result_maturities=[result_maturity],
            result_run_ids=["run_maturity"],
            promoted_run_ids=["run_maturity"],
        )


def test_matrix_allows_missing_maturity_date_when_both_sides_are_missing():
    response = _matrix_response_with_final_results(
        matrix_maturity=None,
        result_maturities=[None],
        result_run_ids=["run_no_maturity"],
        promoted_run_ids=["run_no_maturity"],
    )

    assert response.final_holdout_maturity_date is None
    assert response.final_holdout_results[0].final_holdout_maturity_date is None


def test_method_selection_http_create_reload_and_promoted_run_artifacts(
    monkeypatch,
):
    feature_sets, specs_by_id = service.build_feature_set_manifests()
    manifest = service.build_tuning_candidate_manifests(
        _request(), feature_sets[0]
    )[0]
    final_dates = [date(2024, 1, index) for index in (2, 3, 4)]
    boundary = MethodSelectionFoldBoundary(
        number=6,
        train_market_date_count=10,
        train_date_start=date(2023, 12, 1),
        train_date_end=date(2023, 12, 10),
        purge_market_date_count=5,
        purge_date_start=date(2023, 12, 11),
        purge_date_end=date(2023, 12, 15),
        holdout_market_date_count=len(final_dates),
        holdout_date_start=final_dates[0],
        holdout_date_end=final_dates[-1],
        train_row_count=10,
        target_purge_row_count=1,
        holdout_row_count=3,
    )
    final_evaluation = CalibrationCandidateFoldResult(
        fold_number=6,
        status="evaluated",
        action_row_count=2,
        action_row_threshold_hit_count=1,
        action_row_threshold_hit_rate=0.5,
        mean_realized_excess_return=0.01,
        baseline_relative_mean_net_return=0.002,
    )
    response = MethodSelectionMatrixResponse(
        matrix_id="matrix_reload",
        request_id="request_reload",
        request=_request(),
        feature_registry_version="registry",
        dataset={"requested_symbol_count": 2},
        final_holdout_policy_version=(
            service.METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION
        ),
        final_holdout_market_dates=final_dates,
        fold_policy_version="fold",
        policy_version="policy",
        feature_ablation_policy_version="ablation",
        ranking_policy_version="rank",
        screening_policy_version="screening",
        outer_stability_policy_version="stability",
        feature_sets=[],
        phase_a_candidate_manifests=[],
        phase_b_candidate_manifests=[manifest],
        outer_folds=[],
        outer_candidate_summaries=[],
        shortlist=[
            {
                "candidate_id": manifest.candidate_id,
                "status": "evaluated",
            }
        ],
        final_holdout_results=[
            {
                "shortlisted_candidate_id": manifest.candidate_id,
                "final_candidate_id": manifest.candidate_id,
                "final_candidate_manifest": manifest,
                "final_holdout_policy_version": (
                    service.METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION
                ),
                "final_holdout_market_dates": final_dates,
                "final_holdout_boundary": boundary,
                "final_holdout_evaluation": final_evaluation,
                "status": "promoted",
                "promoted_research_run_id": "run_reload",
            }
        ],
        promoted_research_run_ids=["run_reload"],
        resource_evidence={"wall_clock_seconds": 0, "cpu_seconds": 0},
        comparability_evidence={"policy_version": "common"},
        created_at="2024-01-01T00:00:00Z",
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            MethodSelectionMatrix.__table__,
            ResearchRun.__table__,
            ResearchRunLiquidityCoverage.__table__,
        ],
    )
    testing_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(
        method_selection_repository,
        "SessionLocal",
        testing_session_local,
    )
    monkeypatch.setattr(
        research_run_repository,
        "SessionLocal",
        testing_session_local,
    )
    method_selection_repository.persist_method_selection_matrix(
        response.model_dump(mode="json")
    )
    monkeypatch.setattr(
        research_api,
        "create_method_selection_matrix",
        lambda *args, **kwargs: response,
    )

    created = client.post(
        "/api/v1/research/method-selection-matrices",
        json=_request().model_dump(mode="json"),
    )
    reloaded = client.get(
        "/api/v1/research/method-selection-matrices/matrix_reload"
    )

    assert created.status_code == 200
    assert created.json()["promoted_research_run_ids"] == ["run_reload"]
    assert reloaded.status_code == 200
    assert reloaded.json()["final_holdout_results"][0][
        "final_holdout_policy_version"
    ] == service.METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION
    assert reloaded.json()["final_holdout_results"][0][
        "promoted_research_run_id"
    ] == "run_reload"

    run_request = service._build_promoted_run_request(
        _request(), manifest, specs_by_id
    )
    run_response = ResearchRunResponse.model_validate(
        {
            "run_id": "run_reload",
            "metrics": {
                "total_return": 0.1,
                "sharpe": 1.0,
                "max_drawdown": -0.02,
                "turnover": 0.2,
                "max_position_weight": 1.0,
            },
            "equity_curve": [{"date": final_dates[0], "equity": 1.0}],
            "signals": [
                {
                    "date": final_dates[0],
                    "symbol": "AAA",
                    "score": 1.0,
                    "position": 1.0,
                    "signal_kind": "holdout_evaluation",
                    "up_probability": 0.9,
                    "predicted_direction": "up",
                }
            ],
            "model_diagnostics": {
                "task": "regression",
                "sample_count": 1,
                "rmse": 0.1,
                "mae": 0.1,
            },
            "baselines": {
                "matched_baseline_outcomes": {"mean_net_return": 0.01}
            },
            "runtime_mode": "runtime_compatibility_mode",
            "effective_strategy": {
                "threshold": None,
                "top_n": manifest.top_n,
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": (
                    run_request.strategy.dynamic_threshold_policy.model_dump(
                        mode="json"
                    )
                ),
            },
            "config_sources": {
                "strategy": {
                    "threshold": "derived_policy",
                    "top_n": "request_override",
                }
            },
            "fallback_audit": {
                "strategy": {
                    "threshold": {
                        "attempted": False,
                        "outcome": "not_needed",
                    },
                    "top_n": {
                        "attempted": False,
                        "outcome": "not_needed",
                    },
                }
            },
            **build_version_pack_payload(
                {
                    "threshold_policy_version": manifest.threshold_policy_version,
                    "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                    "benchmark_comparability_gate": False,
                    "comparison_eligibility": "research_only_comparable",
                }
            ),
        }
    )
    registry_service.record_started(
        run_id="run_reload",
        request_id="request_reload:promoted:run_reload",
        request=run_request,
    )
    registry_service.record_success(
        run_id="run_reload",
        request_id="request_reload:promoted:run_reload",
        request=run_request,
        runtime_context={
            "strategy": {
                "threshold": None,
                "top_n": manifest.top_n,
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": (
                    run_request.strategy.dynamic_threshold_policy.model_dump(
                        mode="json"
                    )
                ),
            },
            "config_sources": run_response.config_sources.model_dump(mode="json"),
            "fallback_audit": run_response.fallback_audit.model_dump(mode="json"),
        },
        response=run_response,
        validation_summary=None,
        warnings=[],
        request_payload_extra={
            "matrix_id": "matrix_reload",
            "final_holdout_policy_version": service.METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
        },
    )
    loaded_run = research_run_projection.get_research_run_record("run_reload")

    assert loaded_run["artifact_completeness"] == "complete"
    assert loaded_run["metrics"]["total_return"] == pytest.approx(0.1)
    assert loaded_run["signals"][0]["signal_kind"] == "holdout_evaluation"
    assert loaded_run["model_diagnostics"]["sample_count"] == 1
    assert loaded_run["effective_strategy"]["threshold_mode"] == "dynamic"
    assert loaded_run["effective_strategy"]["threshold"] is None
    assert loaded_run["effective_strategy"]["dynamic_threshold_policy"][
        "horizon_days"
    ] == manifest.horizon_days
    assert loaded_run["request_payload"]["method_selection"]["matrix_id"] == (
        "matrix_reload"
    )


def test_method_selection_rejects_concurrent_matrix():
    assert service._METHOD_SELECTION_ACTIVE.acquire(blocking=False)
    try:
        with pytest.raises(CalibrationBusyError):
            service.create_method_selection_matrix(_request(), request_id="req_busy")
    finally:
        service._METHOD_SELECTION_ACTIVE.release()


def test_method_selection_migration_retains_evidence_on_downgrade():
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).resolve().parents[2] / "backend/alembic/versions/0010_method_selection_matrices.py"
    spec = spec_from_file_location("migration_0010", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()
        connection.execute(text("INSERT INTO method_selection_matrices (matrix_id, request_id, status, request_payload_json, result_payload_json) VALUES ('matrix_1', 'req_1', 'succeeded', '{}', '{}')"))
        with Operations.context(context):
            module.downgrade()
        assert inspect(connection).has_table("method_selection_matrices")
