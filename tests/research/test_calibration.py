from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.research.api as research_api
import backend.research.services.calibration as calibration_service
from backend.app import app
from backend.database import Base, CalibrationMatrix
import backend.research.repositories.calibration as calibration_repository
from backend.platform.errors import (
    CalibrationBusyError,
    CalibrationEvaluationError,
    DataAccessError,
)
from backend.shared.analytics.models import ModelUnavailableError
from backend.shared.analytics.features import FEATURE_REGISTRY_VERSION
from backend.shared.analytics.pooled import (
    FeatureConfigurationError,
    MarketDateFold,
    build_market_date_folds,
)
from backend.research.contracts.calibration import (
    CalibrationArtifactEvidence,
    CalibrationDatasetSummary,
    CalibrationEvaluation,
    CalibrationFoldMetrics,
    CalibrationMatrixCreateRequest,
    CalibrationMatrixResponse,
    CalibrationModelAvailability,
    CalibrationModelResult,
    CalibrationResourceEvidence,
    CalibrationDirectionCalibrationEvidence,
)
from backend.research.policies.calibration import (
    CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION,
    CALIBRATION_MARKET_DATE_AXIS_POLICY_VERSION,
)

client = TestClient(app)


def _request() -> CalibrationMatrixCreateRequest:
    return CalibrationMatrixCreateRequest(
        symbols=["AAA", "BBB"],
        date_range={"start": "2024-01-01", "end": "2024-03-31"},
        features=[{"name": "ma", "window": 2, "source": "close", "shift": 1}],
        model_families=["extra_trees", "xgboost"],
        horizon_days=5,
    )


def _market_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    rows = []
    for symbol, base in (("AAA", 100.0), ("BBB", 200.0)):
        for offset, timestamp in enumerate(dates):
            rows.append(
                {
                    "date": timestamp,
                    "symbol": symbol,
                    "open": base + offset,
                    "high": base + offset + 1,
                    "low": base + offset - 1,
                    "close": base + offset + 0.5,
                    "volume": 1000 + offset,
                    "source": "official",
                }
            )
    return pd.DataFrame(rows)


def _market_dates() -> tuple[date, ...]:
    return tuple(sorted(set(_market_frame()["date"].dt.date)))


def _candidate_market_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=330, freq="D")
    rows = []
    for symbol, phase in (("AAA", 0.0), ("BBB", 0.7), ("CCC", 1.4)):
        for offset, timestamp in enumerate(dates):
            open_price = 100.0 + (8.0 * np.sin(offset / 3.0 + phase)) + offset * 0.03
            rows.append(
                {
                    "date": timestamp,
                    "symbol": symbol,
                    "open": open_price,
                    "high": open_price + 1.0,
                    "low": open_price - 1.0,
                    "close": open_price + 0.25,
                    "volume": 1000 + offset,
                    "source": "official",
                }
            )
    return pd.DataFrame(rows)


def test_calibration_evaluates_grid_and_keeps_ungated_baseline_for_no_opinion(
    monkeypatch,
):
    frame = _candidate_market_frame()
    persisted: list[dict] = []
    monkeypatch.setattr(calibration_service.data_service, "get_data", lambda **_: frame)
    monkeypatch.setattr(
        calibration_service.data_service, "load_official_no_data_dates", lambda **_: set()
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: tuple(sorted(set(frame["date"].dt.date))),
    )

    class _Regressor:
        def predict(self, features: pd.DataFrame) -> np.ndarray:
            return np.linspace(0.01, 0.03, len(features))

    class _Gate:
        def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
            return np.tile([0.9, 0.1], (len(features), 1))

    monkeypatch.setattr(
        calibration_service.model_service, "fit_regressor", lambda **_: _Regressor()
    )
    monkeypatch.setattr(
        calibration_service,
        "_fit_pooled_direction_classifier",
        lambda **_: (
            _Gate(),
            None,
            CalibrationDirectionCalibrationEvidence(base_row_count=20),
        ),
    )
    monkeypatch.setattr(
        calibration_service, "persist_calibration_matrix", lambda payload: persisted.append(payload)
    )
    request = _request().model_copy(
        update={
            "symbols": ["AAA", "BBB", "CCC"],
            "model_families": ["extra_trees"],
        }
    )

    result = calibration_service.create_calibration_matrix(
        request, request_id="req_grid", matrix_id="calibration_grid"
    )

    candidates = result.evaluation.model_results[0].candidate_results
    assert len(result.evaluation.candidate_manifest) == 27
    assert len(candidates) == 27
    assert all(item.status == "no_opinion" for item in candidates)
    assert all(
        fold.matched_baseline_outcomes.participant_count == 0
        for item in candidates
        for fold in item.folds
    )
    assert any(
        fold.eligible_date_reference_baseline_outcomes.participant_count > 0
        for item in candidates
        for fold in item.folds
    )
    assert all(fold.action_row_count == 0 for item in candidates for fold in item.folds)
    assert all(
        fold.action_row_threshold_hit_rate is None
        for item in candidates
        for fold in item.folds
    )
    assert persisted[0]["evaluation"]["candidate_manifest"][0]["horizon_days"] == 5
    assert "shortlist" not in persisted[0]
    assert "research_run_id" not in persisted[0]


def test_calibration_direction_prediction_error_fails_without_persisting(monkeypatch):
    persisted: list[dict] = []
    monkeypatch.setattr(
        calibration_service.data_service, "get_data", lambda **_: _market_frame()
    )
    monkeypatch.setattr(
        calibration_service.data_service, "load_official_no_data_dates", lambda **_: set()
    )
    monkeypatch.setattr(
        calibration_service.data_service, "load_tw_market_dates", lambda **_: _market_dates()
    )

    class _Regressor:
        def predict(self, features: pd.DataFrame) -> np.ndarray:
            return np.linspace(0.001, 0.01, len(features))

    class _BrokenGate:
        def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
            raise RuntimeError("controlled probability failure")

    monkeypatch.setattr(
        calibration_service.model_service, "fit_regressor", lambda **_: _Regressor()
    )
    monkeypatch.setattr(
        calibration_service,
        "_fit_pooled_direction_classifier",
        lambda **_: (_BrokenGate(), None, CalibrationDirectionCalibrationEvidence()),
    )
    monkeypatch.setattr(
        calibration_service, "persist_calibration_matrix", lambda payload: persisted.append(payload)
    )

    with pytest.raises(CalibrationEvaluationError, match="Direction Gate failed"):
        calibration_service.create_calibration_matrix(
            _request().model_copy(update={"model_families": ["extra_trees"]}),
            request_id="req_gate_prediction_failure",
            matrix_id="calibration_gate_prediction_failure",
        )

    assert persisted == []


def test_calibration_candidate_manifest_is_a_stable_horizon_scoped_fixed_grid():
    manifest = calibration_service.build_calibration_candidate_manifest(
        horizon_days=20
    )

    assert len(manifest) == 27
    assert [
        (item.volatility_lookback, item.multiplier, item.top_n)
        for item in manifest
    ] == [
        (lookback, multiplier, top_n)
        for lookback in (20, 60, 252)
        for multiplier in (0.5, 0.75, 1.0)
        for top_n in (5, 10, 20)
    ]
    assert {(item.volatility_lookback, item.multiplier, item.top_n) for item in manifest} == {
        (lookback, multiplier, top_n)
        for lookback in (20, 60, 252)
        for multiplier in (0.5, 0.75, 1.0)
        for top_n in (5, 10, 20)
    }
    assert {item.horizon_days for item in manifest} == {20}
    assert {item.probability_cutoff for item in manifest} == {0.5}
    assert {item.volatility_ddof for item in manifest} == {1}
    assert {item.fee for item in manifest} == {0.002}
    assert {item.slippage for item in manifest} == {0.001}


def test_evaluated_candidate_matches_baseline_dates_and_uses_date_weighted_metrics():
    candidate = calibration_service.build_calibration_candidate_manifest(
        horizon_days=5
    )[0].model_copy(update={"top_n": 2})
    holdout = pd.DataFrame(
        {
            "date": [
                date(2024, 1, 1), date(2024, 1, 1), date(2024, 1, 1),
                date(2024, 1, 2), date(2024, 1, 2), date(2024, 1, 3),
            ],
            "symbol": ["AAA", "BBB", "CCC", "AAA", "BBB", "AAA"],
            "target": [0.02, 0.0, 0.01, 0.02, 0.01, 0.02],
            "open_to_open_volatility_20": [0.01] * 6,
        }
    )
    result = calibration_service._evaluate_candidate_fold(
        candidate=candidate,
        fold=MarketDateFold(
            1, (), (), (date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3))
        ),
        holdout=holdout,
        scores=np.array([0.4, 0.3, 0.2, 0.4, 0.3, 0.4]),
        probabilities=np.array([0.9, 0.9, 0.1, 0.1, 0.1, 0.9]),
        unavailable_reason=None,
        evidence=None,
    )
    assert result.status == "evaluated"
    assert result.candidate_outcomes.signal_market_date_count == 2
    assert result.matched_baseline_outcomes.signal_market_date_count == 2
    assert result.eligible_date_reference_baseline_outcomes.signal_market_date_count == 3
    assert result.action_row_threshold_hit_rate == pytest.approx(0.75)
    assert result.matched_baseline_outcomes.participant_count == 3


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["not_evaluated", "evaluated", "evaluated"], "evaluated"),
        (["not_evaluated", "no_opinion"], "no_opinion"),
        (["not_evaluated"], "not_evaluated"),
    ],
)
def test_candidate_status_rollup_prioritizes_evidence(statuses, expected):
    folds = [
        calibration_service.CalibrationCandidateFoldResult(
            fold_number=index + 1,
            status=status,
            status_reason="unavailable" if status == "not_evaluated" else None,
        )
        for index, status in enumerate(statuses)
    ]
    assert calibration_service._candidate_status(folds) == expected


def test_calibration_service_runs_each_configured_family_without_xgboost_fallback(
    monkeypatch,
):
    persisted: list[dict] = []
    fit_calls: list[dict] = []

    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: _market_frame(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )

    class _Regressor:
        def predict(self, features: pd.DataFrame) -> np.ndarray:
            return np.linspace(0.001, 0.01, len(features))

    def _fit_regressor(*, model_type, X_train, y_train, model_params):
        fit_calls.append(
            {
                "model_type": model_type,
                "rows": len(X_train),
                "params": model_params,
            }
        )
        if model_type == "xgboost":
            raise ModelUnavailableError("xgboost native runtime unavailable")
        return _Regressor()

    monkeypatch.setattr(
        calibration_service.model_service,
        "fit_regressor",
        _fit_regressor,
    )
    monkeypatch.setattr(
        calibration_service,
        "persist_calibration_matrix",
        lambda payload: persisted.append(payload),
    )

    result = calibration_service.create_calibration_matrix(
        _request(),
        request_id="req_calibration",
        matrix_id="calibration_123",
    )

    assert result.matrix_id == "calibration_123"
    assert result.feature_registry_version == FEATURE_REGISTRY_VERSION
    assert result.status == "succeeded"
    assert result.evaluation.status == "evaluated"
    assert result.dataset.model_ready_row_count > 0
    assert len(result.folds) == 3
    assert result.folds[0].holdout_date_start < result.folds[1].holdout_date_start
    assert result.dataset.feature_continuity_policy_version == (
        CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION
    )
    assert result.dataset.market_date_axis_policy_version == (
        CALIBRATION_MARKET_DATE_AXIS_POLICY_VERSION
    )
    assert {item.symbol for item in result.dataset.symbol_coverage} == {
        "AAA",
        "BBB",
    }
    assert all(
        item.canonical_row_count
        == item.model_ready_row_count + item.excluded_canonical_row_count
        for item in result.dataset.symbol_coverage
    )

    availability = {
        item.model_type: item for item in result.evaluation.model_availability
    }
    assert availability["extra_trees"].available is True
    assert availability["extra_trees"].evaluated_fold_count == 3
    assert availability["xgboost"].available is False
    assert "native runtime unavailable" in (availability["xgboost"].reason or "")
    assert all(call["params"]["n_estimators"] == 200 for call in fit_calls)
    assert {call["model_type"] for call in fit_calls} == {"extra_trees", "xgboost"}
    manifest = {
        item.model_type: item for item in result.model_manifest
    }
    assert set(manifest["extra_trees"].presets) == {
        "conservative",
        "balanced",
        "flexible",
    }
    assert manifest["extra_trees"].executed_preset == "balanced"
    evidence = result.evaluation.resource_evidence
    assert evidence.regression_fit_attempt_count == 4
    assert evidence.direction_gate_fit_attempt_count == 27
    assert evidence.model_fit_count == 31
    assert result.comparison_caveats[0].code == (
        "TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE"
    )
    assert result.comparison_caveats[0].severity == "note"
    assert "comparison_caveats" in result.evaluation.artifact_evidence.present_artifacts
    assert (
        result.evaluation.resource_evidence.request_bounds_policy_version
        == "calibration_request_bounds_v1"
    )
    assert (
        result.evaluation.resource_evidence.data_source_policy_version
        == "tw_official_preferred_yfinance_fallback_v1"
    )
    assert result.evaluation.model_availability == [
        item.availability for item in result.evaluation.model_results
    ]
    assert result.evaluation.resource_evidence.deduplicated_market_date_row_count == 0
    assert result.evaluation.artifact_evidence.missing_artifacts == []
    assert "shortlist" not in result.model_dump()
    assert "research_run_id" not in result.model_dump()
    assert len(persisted) == 1
    assert persisted[0]["matrix_id"] == "calibration_123"
    assert persisted[0]["feature_registry_version"] == FEATURE_REGISTRY_VERSION
    assert "feature_registry_version" not in persisted[0]["request"]
    assert "model_availability" not in persisted[0]["evaluation"]


def test_calibration_skips_empty_folds_but_evaluates_later_folds(monkeypatch):
    frame = _market_frame()
    frame = frame.loc[frame["date"] >= pd.Timestamp("2024-01-31")].copy()

    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: frame,
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )

    class _Regressor:
        def predict(self, features: pd.DataFrame) -> np.ndarray:
            return np.linspace(0.001, 0.01, len(features))

    monkeypatch.setattr(
        calibration_service.model_service,
        "fit_regressor",
        lambda **_: _Regressor(),
    )
    monkeypatch.setattr(
        calibration_service,
        "persist_calibration_matrix",
        lambda payload: None,
    )

    result = calibration_service.create_calibration_matrix(
        _request().model_copy(update={"model_families": ["extra_trees"]}),
        request_id="req_empty_fold_continuation",
        matrix_id="calibration_empty_fold_continuation",
    )

    model_result = result.evaluation.model_results[0]
    assert model_result.availability.available is True
    assert model_result.availability.evaluated_fold_count == 1
    assert [fold.evaluation_status for fold in model_result.folds] == [
        "not_evaluated",
        "not_evaluated",
        "evaluated",
    ]


def test_model_family_is_unavailable_when_all_folds_are_empty():
    folds = [
        MarketDateFold(
            number=index,
            train_dates=(date(2024, 1, index),),
            purge_dates=(),
            holdout_dates=(date(2024, 2, index),),
        )
        for index in range(1, 4)
    ]
    empty_rows = calibration_service._PreparedFoldRows(
        raw_train=pd.DataFrame(),
        train=pd.DataFrame(),
        holdout=pd.DataFrame(),
    )

    result, regression_fit_count, direction_gate_fit_count = calibration_service._evaluate_model_family(
        "extra_trees",
        frame=pd.DataFrame(),
        feature_names=("MA_1",),
        folds=folds,
        prepared_rows=[empty_rows, empty_rows, empty_rows],
    )

    assert regression_fit_count == 0
    assert direction_gate_fit_count == 0
    assert result.availability.available is False
    assert result.availability.evaluated_fold_count == 0
    assert result.availability.reason == (
        "Pooled train or holdout rows are unavailable."
    )


def _response(request: CalibrationMatrixCreateRequest) -> CalibrationMatrixResponse:
    return CalibrationMatrixResponse(
        matrix_id="calibration_api",
        request_id="req_api",
        status="succeeded",
        request=request,
        dataset=CalibrationDatasetSummary(
            requested_symbol_count=len(request.symbols),
            model_ready_symbol_count=1,
            model_ready_row_count=10,
            market_date_count=10,
            market_date_start=date(2024, 1, 1),
            market_date_end=date(2024, 1, 10),
            feature_names=["MA_2"],
        ),
        folds=[],
        model_manifest=[],
        evaluation=CalibrationEvaluation(
            status="evaluated",
            model_results=[],
            artifact_evidence=CalibrationArtifactEvidence(
                present_artifacts=["pooled_dataset_summary"]
            ),
            resource_evidence=CalibrationResourceEvidence(
                wall_clock_seconds=0.1,
                cpu_seconds=0.1,
                model_ready_row_count=10,
                feature_count=1,
                fold_count=0,
                model_fit_count=0,
            ),
        ),
        created_at="2026-08-19T00:00:00Z",
    )


def test_public_calibration_api_creates_and_retrieves_a_persisted_matrix(monkeypatch):
    captured: dict[str, object] = {}
    request = _request()
    response = _response(request)

    def _create(request, *, request_id, matrix_id=None):
        captured["request"] = request
        captured["request_id"] = request_id
        return response

    monkeypatch.setattr(research_api, "create_calibration_matrix", _create)
    monkeypatch.setattr(
        research_api,
        "get_calibration_matrix",
        lambda matrix_id: response,
    )

    payload = request.model_dump(mode="json")
    created = client.post(
        "/api/v1/research/calibration-matrices",
        json=payload,
        headers={"X-Request-Id": "req_api"},
    )
    loaded = client.get("/api/v1/research/calibration-matrices/calibration_api")

    assert created.status_code == 200
    assert loaded.status_code == 200
    assert created.json()["matrix_id"] == "calibration_api"
    assert loaded.json()["evaluation"]["status"] == "evaluated"
    assert captured["request_id"] == "req_api"
    assert captured["request"].symbols == ["AAA", "BBB"]


def test_calibration_evaluation_derives_model_availability_from_results():
    availability = CalibrationModelAvailability(
        model_type="extra_trees",
        available=True,
        evaluated_fold_count=1,
    )
    evaluation = CalibrationEvaluation(
        status="evaluated",
        model_availability=[
            CalibrationModelAvailability(
                model_type="random_forest",
                available=False,
            )
        ],
        model_results=[
            CalibrationModelResult(
                model_type="extra_trees",
                availability=availability,
                folds=[],
            )
        ],
        artifact_evidence=CalibrationArtifactEvidence(
            present_artifacts=["model_availability"]
        ),
        resource_evidence=CalibrationResourceEvidence(
            wall_clock_seconds=0.1,
            cpu_seconds=0.1,
        ),
    )

    assert evaluation.model_availability == [availability]


def test_calibration_fold_summary_purges_rows_by_target_end_date():
    dates = tuple(date(2024, 1, 1 + offset) for offset in range(30))
    fold = build_market_date_folds(
        dates,
        splits=3,
        test_size=0.2,
        purge=5,
    )[0]
    rows = [
        {
            "date": train_date,
            "target_end_date": (
                fold.holdout_dates[0]
                if train_date == fold.train_dates[-1]
                else train_date
            ),
        }
        for train_date in fold.train_dates
    ]

    summary = calibration_service._fold_summary(fold, pd.DataFrame(rows))

    assert summary.train_row_count == len(fold.train_dates) - 1
    assert summary.target_purge_row_count == 1


def test_public_calibration_api_rejects_duplicate_model_families():
    payload = _request().model_dump(mode="json")
    payload["model_families"] = ["extra_trees", "extra_trees"]

    response = client.post("/api/v1/research/calibration-matrices", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_public_calibration_api_rejects_duplicate_features():
    payload = _request().model_dump(mode="json")
    payload["features"] = [payload["features"][0], payload["features"][0]]

    response = client.post("/api/v1/research/calibration-matrices", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_calibration_fold_metrics_require_reason_for_not_evaluated():
    with pytest.raises(ValidationError, match="status_reason"):
        CalibrationFoldMetrics(
            fold_number=1,
            evaluation_status="not_evaluated",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbols", [f"S{index}" for index in range(201)]),
        (
            "features",
            [
                {"name": "ma", "window": index + 1, "source": "close", "shift": 1}
                for index in range(13)
            ],
        ),
        (
            "date_range",
            {"start": "2020-01-01", "end": "2025-01-01"},
        ),
    ],
)
def test_public_calibration_api_rejects_requests_over_bounds(field, value):
    payload = _request().model_dump(mode="json")
    payload[field] = value

    response = client.post("/api/v1/research/calibration-matrices", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_calibration_busy_error_has_stable_api_response(monkeypatch):
    def _raise_busy(*args, **kwargs):
        raise CalibrationBusyError(
            "Another Calibration Matrix is already running; retry later."
        )

    monkeypatch.setattr(research_api, "create_calibration_matrix", _raise_busy)

    response = client.post(
        "/api/v1/research/calibration-matrices",
        json=_request().model_dump(mode="json"),
        headers={"X-Request-Id": "req_busy"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert response.json()["error"]["code"] == "CALIBRATION_BUSY"


def test_calibration_active_slot_is_released_after_failure(monkeypatch):
    def _fail(*args, **kwargs):
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(calibration_service, "_build_response", _fail)

    with pytest.raises(RuntimeError, match="controlled failure"):
        calibration_service.create_calibration_matrix(
            _request(),
            request_id="req_failure",
            matrix_id="calibration_failure",
        )

    assert calibration_service._CALIBRATION_ACTIVE.acquire(blocking=False)
    calibration_service._CALIBRATION_ACTIVE.release()


def test_calibration_releases_active_slot_if_start_log_fails(monkeypatch):
    class _Semaphore:
        def __init__(self):
            self.acquired = False

        def acquire(self, blocking=False):
            if self.acquired:
                return False
            self.acquired = True
            return True

        def release(self):
            self.acquired = False

    semaphore = _Semaphore()
    monkeypatch.setattr(calibration_service, "_CALIBRATION_ACTIVE", semaphore)

    def _raise_log_error(*args, **kwargs):
        raise RuntimeError("controlled log failure")

    monkeypatch.setattr(calibration_service.logger, "info", _raise_log_error)

    with pytest.raises(RuntimeError, match="controlled log failure"):
        calibration_service.create_calibration_matrix(
            _request(),
            request_id="req_log_failure",
            matrix_id="calibration_log_failure",
        )

    assert semaphore.acquired is False


def test_calibration_unexpected_model_error_fails_without_persisting(monkeypatch):
    persisted: list[dict] = []

    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: _market_frame(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )

    def _raise_model_bug(**kwargs):
        raise RuntimeError("controlled model bug")

    monkeypatch.setattr(
        calibration_service.model_service,
        "fit_regressor",
        _raise_model_bug,
    )
    monkeypatch.setattr(
        calibration_service,
        "persist_calibration_matrix",
        lambda payload: persisted.append(payload),
    )

    with pytest.raises(
        CalibrationEvaluationError,
        match="failed during evaluation",
    ):
        calibration_service.create_calibration_matrix(
            _request().model_copy(update={"model_families": ["extra_trees"]}),
            request_id="req_model_bug",
            matrix_id="calibration_model_bug",
        )

    assert persisted == []


def test_calibration_data_shape_error_fails_without_persisting(monkeypatch):
    persisted: list[dict] = []

    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: _market_frame().drop(columns=["volume"]),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )
    monkeypatch.setattr(
        calibration_service,
        "persist_calibration_matrix",
        lambda payload: persisted.append(payload),
    )

    with pytest.raises(
        CalibrationEvaluationError,
        match="Calibration dataset could not be prepared",
    ):
        calibration_service.create_calibration_matrix(
            _request().model_copy(update={"model_families": ["extra_trees"]}),
            request_id="req_data_shape_bug",
            matrix_id="calibration_data_shape_bug",
        )

    assert persisted == []


def test_calibration_feature_configuration_error_fails_without_persisting(
    monkeypatch,
):
    persisted: list[dict] = []

    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: _market_frame(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )

    def _raise_feature_configuration_error(**kwargs):
        raise FeatureConfigurationError("feature configuration is invalid")

    monkeypatch.setattr(
        calibration_service,
        "build_pooled_model_ready_dataset",
        _raise_feature_configuration_error,
    )
    monkeypatch.setattr(
        calibration_service,
        "persist_calibration_matrix",
        lambda payload: persisted.append(payload),
    )

    with pytest.raises(
        CalibrationEvaluationError,
        match="Calibration dataset could not be prepared",
    ):
        calibration_service.create_calibration_matrix(
            _request().model_copy(update={"model_families": ["extra_trees"]}),
            request_id="req_feature_configuration_bug",
            matrix_id="calibration_feature_configuration_bug",
        )

    assert persisted == []


def test_public_calibration_api_returns_not_found_for_empty_market_data(monkeypatch):
    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: pd.DataFrame(),
    )

    response = client.post(
        "/api/v1/research/calibration-matrices",
        json=_request().model_dump(mode="json"),
        headers={"X-Request-Id": "req_no_data"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_calibration_rejects_when_active_slot_is_occupied():
    assert calibration_service._CALIBRATION_ACTIVE.acquire(blocking=False)
    try:
        with pytest.raises(CalibrationBusyError):
            calibration_service.create_calibration_matrix(
                _request(),
                request_id="req_busy_direct",
                matrix_id="calibration_busy",
            )
    finally:
        calibration_service._CALIBRATION_ACTIVE.release()


def test_public_calibration_api_persists_and_reloads_matrix(monkeypatch, request):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    request.addfinalizer(engine.dispose)
    Base.metadata.tables["calibration_matrices"].create(engine)
    monkeypatch.setattr(
        calibration_repository,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, autocommit=False),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "get_data",
        lambda **_: _market_frame(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_official_no_data_dates",
        lambda **_: set(),
    )
    monkeypatch.setattr(
        calibration_service.data_service,
        "load_tw_market_dates",
        lambda **_: _market_dates(),
    )

    class _Regressor:
        def predict(self, features: pd.DataFrame) -> np.ndarray:
            return np.linspace(0.001, 0.01, len(features))

    monkeypatch.setattr(
        calibration_service.model_service,
        "fit_regressor",
        lambda **_: _Regressor(),
    )
    calibration_request = _request().model_copy(
        update={"model_families": ["extra_trees"]}
    )

    created = client.post(
        "/api/v1/research/calibration-matrices",
        json=calibration_request.model_dump(mode="json"),
    )
    matrix_id = created.json()["matrix_id"]
    loaded = client.get(f"/api/v1/research/calibration-matrices/{matrix_id}")

    assert created.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json() == created.json()
    assert len(loaded.json()["evaluation"]["candidate_manifest"]) == 27
    assert len(
        loaded.json()["evaluation"]["model_results"][0]["candidate_results"]
    ) == 27
    assert loaded.json()["comparison_caveats"][0]["code"] == (
        "TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE"
    )
    with calibration_repository.SessionLocal() as session:
        row = session.get(CalibrationMatrix, matrix_id)
        request_payload = calibration_repository.json_loads(
            row.request_payload_json,
            {},
        )
        result_payload = calibration_repository.json_loads(
            row.result_payload_json,
            {},
        )
    assert "feature_registry_version" not in request_payload
    assert result_payload["feature_registry_version"] == FEATURE_REGISTRY_VERSION


def test_persist_calibration_matrix_rejects_missing_request(monkeypatch):
    class _Session:
        added = False
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def get(self, *_args):
            return None

        def add(self, _row):
            self.added = True

        def commit(self):
            self.committed = True

        def refresh(self, _row):
            return None

    session = _Session()
    monkeypatch.setattr(calibration_repository, "SessionLocal", lambda: session)

    with pytest.raises(DataAccessError):
        calibration_repository.persist_calibration_matrix(
            {
                "matrix_id": "missing-request",
                "request_id": "request-missing",
                "status": "succeeded",
            }
        )

    assert session.committed is False
    assert session.added is False
