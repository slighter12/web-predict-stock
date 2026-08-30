from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

import backend.research.api as research_api
import backend.research.services.method_selection as service
from backend.app import app
from backend.platform.errors import CalibrationBusyError, CalibrationEvaluationError
from backend.research.contracts.calibration import CalibrationCandidateFoldResult
from backend.research.contracts.method_selection import (
    MethodCandidateSummary,
    MethodSelectionMatrixCreateRequest,
    MethodSelectionMatrixResponse,
)
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


def test_load_dataset_excludes_final_holdout_and_passes_common_row_policy(monkeypatch):
    feature_sets, specs_by_id = service.build_feature_set_manifests()
    feature_names = {
        feature_set_id: tuple(item.feature_names)
        for feature_set_id, item in ((item.feature_set_id, item) for item in feature_sets)
    }
    dates = tuple(date(2020, 1, 1) + timedelta(days=index) for index in range(400))
    raw = pd.DataFrame({"date": dates, "symbol": ["AAA"] * len(dates), "open": [1.] * len(dates), "high": [1.] * len(dates), "low": [1.] * len(dates), "close": [1.] * len(dates), "volume": [1.] * len(dates)})
    dataset = PooledModelReadyDataset(frame=pd.DataFrame({"date": dates[:-252], "symbol": ["AAA"] * 148}), feature_names=feature_names["full"], exclusions=(), market_dates=dates[:-252])
    captured = {}
    monkeypatch.setattr(service.calibration_service, "_load_market_frame", lambda *_: (raw, dates))
    monkeypatch.setattr(service, "build_pooled_model_ready_dataset", lambda *args, **kwargs: captured.update(kwargs) or dataset)

    _, selection_dates, final_dates = service._load_dataset(
        _request(), specs_by_id["full"], feature_names
    )

    assert selection_dates == dates[:-252]
    assert final_dates == dates[-252:]
    assert captured["market_dates"] == selection_dates
    assert captured["counterfactual_feature_sets"] == feature_names
    assert captured["complete_case_extra_columns"] == (
        "open_to_open_volatility_20", "open_to_open_volatility_60", "open_to_open_volatility_252"
    )


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
        "_load_dataset",
        lambda *_: (dataset, selection_dates, dates[-252:]),
    )
    monkeypatch.setattr(service, "_evaluate_group", fake_evaluate)
    monkeypatch.setattr(service, "persist_method_selection_matrix", persisted.append)
    monkeypatch.setattr(service.calibration_service, "_peak_rss_bytes", lambda: 123)

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
        if len(folds) == 3 and manifests[0].phase == "parameter_search"
    ]
    assert len(phase_b_calls) == 5
    assert all(
        {manifest.feature_set_id for manifest in manifests} == {"baseline"}
        for manifests in phase_b_calls
    )
    assert response.final_holdout_market_dates == list(dates[-252:])
    assert all(
        set(boundary_dates(record.outer_fold)).isdisjoint(dates[-252:])
        for record in response.outer_folds
    )
    assert response.resource_evidence.peak_rss_bytes == 123
    assert response.resource_evidence.deduplicated_market_date_row_count == 7
    assert response.comparability_evidence.common_policy_rows_lost_by_feature_set["baseline"] == 3
    assert persisted[0]["matrix_id"] == "matrix"
    assert response.comparability_evidence.selection_market_date_count == len(selection_dates)
    assert response.comparability_evidence.common_market_date_count == len(model_ready_dates)


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
