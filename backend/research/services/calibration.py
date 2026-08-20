from __future__ import annotations

import logging
import math
import resource
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.market_data.services import research_inputs as data_service
from backend.platform.errors import (
    CalibrationBusyError,
    CalibrationEvaluationError,
    DataNotFoundError,
    InsufficientDataError,
)
from backend.platform.time import utc_now
from backend.research.contracts.calibration import (
    CalibrationArtifactEvidence,
    CalibrationDatasetSummary,
    CalibrationEvaluation,
    CalibrationFoldMetrics,
    CalibrationFoldSummary,
    CalibrationMatrixCreateRequest,
    CalibrationMatrixResponse,
    CalibrationModelAvailability,
    CalibrationModelManifest,
    CalibrationModelResult,
    CalibrationResourceEvidence,
    CalibrationSymbolCoverage,
    CalibrationSymbolExclusion,
)
from backend.research.contracts.runs import ComparisonCaveat
from backend.research.domain.result_caveats import (
    tw_point_in_time_membership_caveat,
)
from backend.research.policies.calibration import (
    CALIBRATION_CAPACITY_PRESET_VERSION,
    CALIBRATION_DATA_SOURCE_POLICY_VERSION,
    CALIBRATION_EXECUTED_PRESET,
    CALIBRATION_FOLD_COUNT,
    CALIBRATION_SOURCE_PRIORITY,
    CALIBRATION_TEST_SIZE,
    capacity_presets_for,
)
from backend.research.repositories.calibration import (
    get_calibration_matrix_snapshot,
    persist_calibration_matrix,
)
from backend.shared.analytics import features as feature_engine
from backend.shared.analytics import models as model_service
from backend.shared.analytics.models import ModelUnavailableError
from backend.shared.analytics.pooled import (
    MarketDateFold,
    PooledModelReadyDataset,
    build_market_date_folds,
    build_pooled_model_ready_dataset,
)

logger = logging.getLogger(__name__)
_CALIBRATION_ACTIVE = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class _PreparedFoldRows:
    raw_train: pd.DataFrame
    train: pd.DataFrame
    holdout: pd.DataFrame


def _feature_config(
    request: CalibrationMatrixCreateRequest,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    config: dict[str, list[dict[str, Any]]] = {}
    shift_map: dict[str, int] = {}
    for spec in request.features:
        config.setdefault(spec.name, []).append(
            {"window": spec.window, "source": spec.source}
        )
        shift_map[feature_engine.feature_col_name(spec.name, spec.window, spec.source)] = (
            spec.shift
        )
    return config, shift_map


def _load_market_frame(
    request: CalibrationMatrixCreateRequest,
) -> tuple[pd.DataFrame, tuple[date, ...]]:
    frame = data_service.get_data(
        symbols=request.symbols,
        start_date=request.date_range.start,
        end_date=request.date_range.end,
        market=request.market,
    )
    if frame.empty:
        return frame, ()

    official_no_data_dates = data_service.load_official_no_data_dates(
        start_date=request.date_range.start,
        end_date=request.date_range.end,
    )
    if "source" in frame.columns:
        normalized = frame.reset_index()
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"])
        normalized.index = normalized["date"]
        frame = data_service.exclude_non_official_rows_on_official_no_data(
            normalized,
            official_no_data_dates,
        ).reset_index(drop=True)
    market_dates = data_service.load_tw_market_dates(
        start_date=request.date_range.start,
        end_date=request.date_range.end,
        official_no_data_dates=official_no_data_dates,
    )
    return frame, market_dates


def _date_bounds(values: tuple) -> tuple[Any | None, Any | None]:
    if not values:
        return None, None
    return values[0], values[-1]


def _rows_for_dates(frame: pd.DataFrame, dates: tuple) -> pd.DataFrame:
    return frame.loc[frame["date"].isin(dates)]


def _training_rows_for_fold(
    fold: MarketDateFold,
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Keep only train rows whose labels settle before the holdout starts."""
    train = _rows_for_dates(frame, fold.train_dates)
    if train.empty:
        return train
    if "target_end_date" not in train.columns:
        raise CalibrationEvaluationError(
            "Calibration dataset is missing target boundary metadata."
        )
    target_end = train["target_end_date"]
    if not pd.api.types.is_datetime64_any_dtype(target_end):
        target_end = pd.to_datetime(target_end, errors="coerce")
    return train.loc[
        target_end.notna()
        & (target_end < pd.Timestamp(fold.holdout_dates[0]))
    ]


def _prepare_fold_rows(
    fold: MarketDateFold,
    frame: pd.DataFrame,
) -> _PreparedFoldRows:
    raw_train = _rows_for_dates(frame, fold.train_dates)
    return _PreparedFoldRows(
        raw_train=raw_train,
        train=_training_rows_for_fold(fold, frame),
        holdout=_rows_for_dates(frame, fold.holdout_dates),
    )


def _fold_summary(
    fold: MarketDateFold,
    frame: pd.DataFrame,
    *,
    prepared_rows: _PreparedFoldRows | None = None,
) -> CalibrationFoldSummary:
    train_start, train_end = _date_bounds(fold.train_dates)
    purge_start, purge_end = _date_bounds(fold.purge_dates)
    holdout_start, holdout_end = _date_bounds(fold.holdout_dates)
    prepared_rows = prepared_rows or _prepare_fold_rows(fold, frame)
    return CalibrationFoldSummary(
        number=fold.number,
        train_market_date_count=len(fold.train_dates),
        train_date_start=train_start,
        train_date_end=train_end,
        purge_market_date_count=len(fold.purge_dates),
        purge_date_start=purge_start,
        purge_date_end=purge_end,
        holdout_market_date_count=len(fold.holdout_dates),
        holdout_date_start=holdout_start,
        holdout_date_end=holdout_end,
        train_row_count=len(prepared_rows.train),
        target_purge_row_count=(
            len(prepared_rows.raw_train) - len(prepared_rows.train)
        ),
        holdout_row_count=len(prepared_rows.holdout),
    )


def _finite_correlation(actual: pd.Series, predicted: np.ndarray, method: str) -> float | None:
    if len(actual) < 2:
        return None
    value = actual.reset_index(drop=True).corr(
        pd.Series(predicted),
        method=method,
    )
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def _failure_reason(exc: Exception) -> str:
    detail = str(exc).strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _not_evaluated_fold(number: int, reason: str) -> CalibrationFoldMetrics:
    return CalibrationFoldMetrics(
        fold_number=number,
        evaluation_status="not_evaluated",
        status_reason=reason,
    )


def _evaluate_model_family(
    model_type: str,
    *,
    frame: pd.DataFrame,
    feature_names: tuple[str, ...],
    folds: list[MarketDateFold],
    prepared_rows: list[_PreparedFoldRows] | None = None,
) -> tuple[CalibrationModelResult, int]:
    params = capacity_presets_for(model_type)[CALIBRATION_EXECUTED_PRESET]
    fold_metrics: list[CalibrationFoldMetrics] = []
    evaluated_fold_count = 0
    fit_attempt_count = 0
    failure_reason: str | None = None

    prepared_rows = prepared_rows or [
        _prepare_fold_rows(fold, frame) for fold in folds
    ]
    for fold, fold_rows in zip(folds, prepared_rows):
        if failure_reason is not None:
            fold_metrics.append(
                _not_evaluated_fold(
                    fold.number,
                    f"Model family unavailable after an earlier fold: {failure_reason}",
                )
            )
            continue

        train = fold_rows.train
        holdout = fold_rows.holdout
        if train.empty or holdout.empty:
            failure_reason = "Pooled train or holdout rows are unavailable."
            fold_metrics.append(
                _not_evaluated_fold(
                    fold.number,
                    failure_reason,
                )
            )
            continue

        try:
            fit_attempt_count += 1
            model = model_service.fit_regressor(
                model_type=model_type,
                X_train=train.loc[:, list(feature_names)],
                y_train=train["target"],
                model_params=params,
            )
            predicted = np.asarray(
                model.predict(holdout.loc[:, list(feature_names)])
            ).reshape(-1)
            if len(predicted) != len(holdout) or not np.isfinite(predicted).all():
                raise ValueError("model produced a non-finite or misaligned prediction")
            actual = holdout["target"].reset_index(drop=True)
            metrics = {
                "sample_count": len(actual),
                "rmse": math.sqrt(mean_squared_error(actual, predicted)),
                "mae": mean_absolute_error(actual, predicted),
                "rank_ic": _finite_correlation(actual, predicted, "spearman"),
                "linear_ic": _finite_correlation(actual, predicted, "pearson"),
            }
        except ModelUnavailableError as exc:
            failure_reason = _failure_reason(exc)
            fold_metrics.append(_not_evaluated_fold(fold.number, failure_reason))
            continue
        except Exception as exc:
            logger.exception(
                "Calibration model evaluation failed model_type=%s fold=%s",
                model_type,
                fold.number,
            )
            raise CalibrationEvaluationError(
                f"Calibration model family '{model_type}' failed during evaluation."
            ) from exc

        fold_metrics.append(
            CalibrationFoldMetrics(
                fold_number=fold.number,
                evaluation_status="evaluated",
                **metrics,
            )
        )
        evaluated_fold_count += 1

    availability = CalibrationModelAvailability(
        model_type=model_type,
        available=failure_reason is None and evaluated_fold_count > 0,
        reason=failure_reason,
        evaluated_fold_count=evaluated_fold_count,
    )
    return (
        CalibrationModelResult(
            model_type=model_type,
            availability=availability,
            folds=fold_metrics,
        ),
        fit_attempt_count,
    )


def _peak_rss_bytes() -> int | None:
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (AttributeError, OSError, ValueError):
        return None
    if sys.platform != "darwin":
        value *= 1024
    return max(value, 0)


def _dataset_summary(
    request: CalibrationMatrixCreateRequest,
    dataset: PooledModelReadyDataset,
) -> CalibrationDatasetSummary:
    dates = dataset.market_dates or tuple(sorted(set(dataset.frame["date"])))
    start, end = _date_bounds(dates)
    return CalibrationDatasetSummary(
        requested_symbol_count=len(request.symbols),
        model_ready_symbol_count=dataset.frame["symbol"].nunique(),
        model_ready_row_count=len(dataset.frame),
        market_date_count=len(dates),
        market_date_start=start,
        market_date_end=end,
        feature_names=list(dataset.feature_names),
        exclusions=[
            CalibrationSymbolExclusion(
                symbol=item.symbol,
                reason=item.reason,
                excluded_row_count=item.excluded_row_count,
            )
            for item in dataset.exclusions
        ],
        symbol_coverage=[
            CalibrationSymbolCoverage(
                symbol=item.symbol,
                canonical_row_count=item.canonical_row_count,
                market_date_axis_row_count=item.market_date_axis_row_count,
                missing_market_date_row_count=item.missing_market_date_row_count,
                invalid_ohlcv_row_count=item.invalid_ohlcv_row_count,
                model_ready_row_count=item.model_ready_row_count,
                excluded_canonical_row_count=item.excluded_canonical_row_count,
            )
            for item in dataset.symbol_coverage
        ],
    )


def _build_response(
    request: CalibrationMatrixCreateRequest,
    *,
    request_id: str,
    matrix_id: str,
) -> CalibrationMatrixResponse:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    frame, market_dates = _load_market_frame(request)
    if frame.empty:
        raise DataNotFoundError(
            "No market data found for the requested symbols and date range."
        )
    feature_config, shift_map = _feature_config(request)
    dataset = build_pooled_model_ready_dataset(
        frame,
        feature_config=feature_config,
        shift_map=shift_map,
        return_target=request.return_target,
        horizon_days=request.horizon_days,
        requested_symbols=request.symbols,
        market_dates=market_dates,
        source_priority=CALIBRATION_SOURCE_PRIORITY,
    )
    if dataset.frame.empty:
        raise InsufficientDataError(
            "Calibration Matrix has no pooled Model-Ready Universe rows."
        )

    try:
        folds = build_market_date_folds(
            dataset.market_dates,
            splits=CALIBRATION_FOLD_COUNT,
            test_size=CALIBRATION_TEST_SIZE,
            purge=request.horizon_days,
        )
    except ValueError as exc:
        raise InsufficientDataError(str(exc)) from exc

    prepared_fold_rows = [
        _prepare_fold_rows(fold, dataset.frame) for fold in folds
    ]
    fold_summaries = [
        _fold_summary(fold, dataset.frame, prepared_rows=prepared)
        for fold, prepared in zip(folds, prepared_fold_rows)
    ]
    model_manifests = [
        CalibrationModelManifest(
            model_type=model_type,
            presets=capacity_presets_for(model_type),
            policy_version=CALIBRATION_CAPACITY_PRESET_VERSION,
        )
        for model_type in request.model_families
    ]

    model_results: list[CalibrationModelResult] = []
    model_fit_count = 0
    for model_type in request.model_families:
        result, fit_count = _evaluate_model_family(
            model_type,
            frame=dataset.frame,
            feature_names=dataset.feature_names,
            folds=folds,
            prepared_rows=prepared_fold_rows,
        )
        model_results.append(result)
        model_fit_count += fit_count

    availability = [result.availability for result in model_results]
    evaluated = any(item.evaluated_fold_count > 0 for item in availability)
    evaluation_status = "evaluated" if evaluated else "not_evaluated"
    status_reason = None if evaluated else "No configured model family completed a fold."
    caveat_payload = tw_point_in_time_membership_caveat(
        market=request.market,
        request_payload=request.model_dump(mode="json"),
    )
    comparison_caveats = (
        [ComparisonCaveat.model_validate(caveat_payload)]
        if caveat_payload
        else []
    )
    present_artifacts = [
        "request",
        "pooled_dataset_summary",
        "market_date_fold_boundaries",
        "capacity_preset_manifest",
        "model_availability",
        "fold_model_summaries",
        "resource_evidence",
    ]
    if comparison_caveats:
        present_artifacts.append("comparison_caveats")
    resource_evidence = CalibrationResourceEvidence(
        wall_clock_seconds=max(time.perf_counter() - started_wall, 0.0),
        cpu_seconds=max(time.process_time() - started_cpu, 0.0),
        peak_rss_bytes=_peak_rss_bytes(),
        data_source_policy_version=CALIBRATION_DATA_SOURCE_POLICY_VERSION,
        model_ready_row_count=len(dataset.frame),
        feature_count=len(dataset.feature_names),
        fold_count=len(folds),
        model_fit_count=model_fit_count,
        deduplicated_market_date_row_count=dataset.deduplicated_row_count,
    )
    evaluation = CalibrationEvaluation(
        status=evaluation_status,
        status_reason=status_reason,
        model_results=model_results,
        artifact_evidence=CalibrationArtifactEvidence(
            completeness="complete",
            present_artifacts=present_artifacts,
        ),
        resource_evidence=resource_evidence,
    )
    return CalibrationMatrixResponse(
        matrix_id=matrix_id,
        request_id=request_id,
        status="succeeded",
        request=request,
        dataset=_dataset_summary(request, dataset),
        folds=fold_summaries,
        model_manifest=model_manifests,
        comparison_caveats=comparison_caveats,
        evaluation=evaluation,
        created_at=utc_now(),
    )


def create_calibration_matrix(
    request: CalibrationMatrixCreateRequest,
    *,
    request_id: str,
    matrix_id: str | None = None,
) -> CalibrationMatrixResponse:
    matrix_id = matrix_id or f"calibration_{uuid4().hex}"
    if not _CALIBRATION_ACTIVE.acquire(blocking=False):
        logger.warning(
            "Calibration Matrix rejected as busy request_id=%s symbol_count=%s "
            "feature_count=%s",
            request_id,
            len(request.symbols),
            len(request.features),
        )
        raise CalibrationBusyError(
            "Another Calibration Matrix is already running; retry later."
        )

    logger.info(
        "Calibration Matrix started request_id=%s matrix_id=%s symbol_count=%s "
        "feature_count=%s date_start=%s date_end=%s",
        request_id,
        matrix_id,
        len(request.symbols),
        len(request.features),
        request.date_range.start,
        request.date_range.end,
    )
    try:
        response = _build_response(
            request,
            request_id=request_id,
            matrix_id=matrix_id,
        )
        persisted_payload = response.model_dump(mode="json")
        # ``model_availability`` is a computed response projection. Keep the
        # persisted representation canonical by storing availability only in
        # each model result.
        persisted_payload["evaluation"].pop("model_availability", None)
        persist_calibration_matrix(persisted_payload)
    except Exception as exc:
        logger.warning(
            "Calibration Matrix unavailable request_id=%s matrix_id=%s "
            "error_type=%s",
            request_id,
            matrix_id,
            type(exc).__name__,
        )
        raise
    else:
        logger.info(
            "Calibration Matrix completed request_id=%s matrix_id=%s "
            "model_ready_row_count=%s evaluation_status=%s wall_clock_seconds=%s",
            request_id,
            matrix_id,
            response.evaluation.resource_evidence.model_ready_row_count,
            response.evaluation.status,
            response.evaluation.resource_evidence.wall_clock_seconds,
        )
        return response
    finally:
        _CALIBRATION_ACTIVE.release()


def get_calibration_matrix(matrix_id: str) -> CalibrationMatrixResponse:
    return CalibrationMatrixResponse.model_validate(
        get_calibration_matrix_snapshot(matrix_id)
    )
