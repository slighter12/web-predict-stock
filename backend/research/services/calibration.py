from __future__ import annotations

import logging
import math
import resource
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date
from itertools import product
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
    CalibrationCandidateFoldResult,
    CalibrationCandidateEvaluationPolicy,
    CalibrationCandidateManifest,
    CalibrationCandidateResult,
    CalibrationDatasetSummary,
    CalibrationDirectionCalibrationEvidence,
    CalibrationEvaluation,
    CalibrationFoldMetrics,
    CalibrationFoldSummary,
    CalibrationMatrixCreateRequest,
    CalibrationMatrixResponse,
    CalibrationModelAvailability,
    CalibrationModelManifest,
    CalibrationModelResult,
    CalibrationOutcomeMetrics,
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
    CALIBRATION_CANDIDATE_GRID_POLICY_VERSION,
    CALIBRATION_DIRECTION_PROBABILITY_CUTOFF,
    CALIBRATION_DIRECTION_CALIBRATION_TAIL_FRACTION,
    CALIBRATION_DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT,
    CALIBRATION_DIRECTION_CALIBRATION_MIN_SAMPLES,
    CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
    CALIBRATION_FEE,
    CALIBRATION_DATA_SOURCE_POLICY_VERSION,
    CALIBRATION_EXECUTED_PRESET,
    CALIBRATION_FOLD_COUNT,
    CALIBRATION_SOURCE_PRIORITY,
    CALIBRATION_SLIPPAGE,
    CALIBRATION_TEST_SIZE,
    CALIBRATION_TOP_N_VALUES,
    CALIBRATION_VOLATILITY_LOOKBACKS,
    CALIBRATION_VOLATILITY_MULTIPLIERS,
    capacity_presets_for,
)
from backend.research.repositories.calibration import (
    get_calibration_matrix_snapshot,
    persist_calibration_matrix,
)
from backend.research.services.feature_config import build_feature_config
from backend.shared.analytics import models as model_service
from backend.shared.analytics.features import FEATURE_REGISTRY_VERSION
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


@dataclass(frozen=True)
class CandidateActionSelection:
    """The canonical threshold, gate, and top-N selection for one candidate."""

    scored: pd.DataFrame
    eligible: pd.DataFrame
    gated: pd.DataFrame
    actions: pd.DataFrame
    thresholds: pd.Series


def _candidate_id(
    *, horizon_days: int, lookback: int, multiplier: float, top_n: int
) -> str:
    multiplier_token = str(multiplier).replace(".", "p")
    return f"h{horizon_days}_l{lookback}_m{multiplier_token}_n{top_n}"


def build_calibration_candidate_manifest(
    *, horizon_days: int
) -> list[CalibrationCandidateManifest]:
    """Return the fixed, ordered calibration grid for one Horizon."""
    return [
        CalibrationCandidateManifest(
            candidate_id=_candidate_id(
                horizon_days=horizon_days,
                lookback=lookback,
                multiplier=multiplier,
                top_n=top_n,
            ),
            horizon_days=horizon_days,
            volatility_lookback=lookback,
            multiplier=multiplier,
            top_n=top_n,
        )
        for lookback, multiplier, top_n in product(
            CALIBRATION_VOLATILITY_LOOKBACKS,
            CALIBRATION_VOLATILITY_MULTIPLIERS,
            CALIBRATION_TOP_N_VALUES,
        )
    ]


def _feature_config(
    request: CalibrationMatrixCreateRequest,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    return build_feature_config(request.features)


def _load_market_frame(
    request: CalibrationMatrixCreateRequest,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[pd.DataFrame, tuple[date, ...]]:
    query_start = start_date or request.date_range.start
    query_end = end_date or request.date_range.end
    frame = data_service.get_data(
        symbols=request.symbols,
        start_date=query_start,
        end_date=query_end,
        market=request.market,
    )
    if frame.empty:
        return frame, ()

    official_no_data_dates = data_service.load_official_no_data_dates(
        start_date=query_start,
        end_date=query_end,
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
        start_date=query_start,
        end_date=query_end,
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


def _candidate_thresholds(
    frame: pd.DataFrame,
    candidate: CalibrationCandidateManifest,
) -> pd.Series:
    column = f"open_to_open_volatility_{candidate.volatility_lookback}"
    if column not in frame.columns:
        raise CalibrationEvaluationError(
            f"Calibration dataset is missing required volatility column '{column}'."
        )
    volatility = pd.to_numeric(frame[column], errors="coerce")
    return volatility * candidate.multiplier * math.sqrt(candidate.horizon_days)


def _positive_class_probabilities(
    classifier: Any,
    features: pd.DataFrame,
) -> np.ndarray:
    probabilities = np.asarray(classifier.predict_proba(features))
    if probabilities.ndim != 2 or probabilities.shape[0] != len(features):
        raise ValueError("Direction Gate produced misaligned probabilities.")

    classes = getattr(classifier, "classes_", None)
    if classes is not None:
        class_values = list(np.asarray(classes).reshape(-1))
        if len(class_values) != probabilities.shape[1]:
            raise ValueError("Direction Gate classes do not match probability columns.")
        if 1 not in class_values:
            raise ValueError("Direction Gate classifier has no positive class.")
        positive_index = class_values.index(1)
    elif probabilities.shape[1] == 1:
        # Compatibility with lightweight test doubles and legacy classifiers that
        # do not expose classes_. Real sklearn classifiers expose classes_.
        positive_index = 0
    else:
        positive_index = 1

    result = probabilities[:, positive_index].reshape(-1)
    if len(result) != len(features) or not np.isfinite(result).all():
        raise ValueError("Direction Gate produced invalid probabilities.")
    return result


def _class_counts(labels: pd.Series) -> dict[str, int]:
    return {
        "negative": int((labels == 0).sum()),
        "positive": int((labels == 1).sum()),
    }


def _fit_pooled_direction_classifier(
    *,
    train: pd.DataFrame,
    feature_names: tuple[str, ...],
    candidate: CalibrationCandidateManifest,
    model_type: str,
    model_params: dict[str, Any],
) -> tuple[object | None, str | None, CalibrationDirectionCalibrationEvidence]:
    """Fit a calibrated gate while keeping every Market Date on one side."""
    threshold = _candidate_thresholds(train, candidate)
    usable = train.loc[np.isfinite(threshold)].copy()
    usable["_direction_threshold"] = threshold.loc[usable.index]
    usable = usable.sort_values(["date", "symbol"]).reset_index(drop=True)
    dates = tuple(sorted(set(usable["date"])))
    if not dates:
        return None, (
            f"No rows have a complete {candidate.volatility_lookback}-return volatility window "
            f"({CALIBRATION_DIRECTION_GATE_POLICY_VERSION})."
        ), CalibrationDirectionCalibrationEvidence()
    if len(dates) < 2:
        return None, (
            "Direction Gate needs at least two threshold-eligible Market Dates "
            f"({CALIBRATION_DIRECTION_GATE_POLICY_VERSION})."
        ), CalibrationDirectionCalibrationEvidence()

    tail_count = max(1, math.ceil(len(dates) * CALIBRATION_DIRECTION_CALIBRATION_TAIL_FRACTION))
    calibration_dates = dates[-tail_count:]
    calibration_start = calibration_dates[0]
    pre_tail = usable.loc[usable["date"] < calibration_start]
    base = pre_tail.loc[
        pd.to_datetime(pre_tail["target_end_date"], errors="coerce")
        < pd.Timestamp(calibration_start)
    ].copy()
    calibration = usable.loc[usable["date"].isin(calibration_dates)].copy()
    base_labels = (base["target"] >= base["_direction_threshold"]).astype(int)
    calibration_labels = (
        calibration["target"] >= calibration["_direction_threshold"]
    ).astype(int)
    evidence = CalibrationDirectionCalibrationEvidence(
        calibration_date_start=calibration_start,
        calibration_date_end=calibration_dates[-1],
        base_market_date_count=base["date"].nunique(),
        calibration_market_date_count=len(calibration_dates),
        base_row_count=len(base),
        calibration_row_count=len(calibration),
        target_purge_row_count=len(pre_tail) - len(base),
        base_class_counts=_class_counts(base_labels),
        calibration_class_counts=_class_counts(calibration_labels),
    )
    try:
        model, reason = model_service.fit_partitioned_calibrated_direction_classifier(
            model_type=model_type,
            X_base=base.loc[:, list(feature_names)],
            y_base=base_labels,
            X_calibration=calibration.loc[:, list(feature_names)],
            y_calibration=calibration_labels,
            model_params=model_params,
            minimum_samples=CALIBRATION_DIRECTION_CALIBRATION_MIN_SAMPLES,
            minimum_class_support=CALIBRATION_DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT,
            policy_version=CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
        )
        if model is None:
            return None, reason, evidence
    except ModelUnavailableError as exc:
        return None, _failure_reason(exc), evidence
    except Exception as exc:
        logger.exception(
            "Pooled Direction Gate calibration failed model_type=%s", model_type
        )
        raise CalibrationEvaluationError(
            "Calibration Direction Gate failed during evaluation."
        ) from exc
    return model, None, evidence


def _select_scored_rows(rows: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    finite = rows.loc[np.isfinite(pd.to_numeric(rows["score"], errors="coerce"))].copy()
    if finite.empty:
        return finite
    return (
        finite.sort_values(
            ["date", "score", "symbol"],
            ascending=[True, False, True],
            kind="stable",
        )
        .groupby("date", sort=True, group_keys=False)
        .head(top_n)
    )


def select_candidate_actions(
    *,
    candidate: CalibrationCandidateManifest,
    holdout: pd.DataFrame,
    scores: np.ndarray,
    probabilities: np.ndarray | None,
) -> CandidateActionSelection:
    """Apply the frozen threshold -> gate -> top-N action-row semantics."""
    scored = holdout.copy()
    normalized_scores = np.asarray(scores).reshape(-1)
    if len(normalized_scores) != len(scored):
        raise ValueError("Candidate scores are not aligned with holdout rows.")
    scored["score"] = normalized_scores
    thresholds = _candidate_thresholds(scored, candidate)
    scored["threshold"] = thresholds
    threshold_available = np.isfinite(thresholds)
    eligible = scored.loc[
        threshold_available
        & np.isfinite(pd.to_numeric(scored["score"], errors="coerce"))
    ].copy()
    if probabilities is None:
        gated = scored.iloc[0:0].copy()
    else:
        normalized_probabilities = np.asarray(probabilities).reshape(-1)
        if len(normalized_probabilities) != len(scored):
            raise ValueError("Direction Gate probabilities are not aligned with holdout rows.")
        scored["probability"] = normalized_probabilities
        gated = scored.loc[
            threshold_available
            & np.isfinite(pd.to_numeric(scored["score"], errors="coerce"))
            & np.isfinite(pd.to_numeric(scored["probability"], errors="coerce"))
            & (
                scored["probability"]
                >= CALIBRATION_DIRECTION_PROBABILITY_CUTOFF
            )
        ].copy()
    return CandidateActionSelection(
        scored=scored,
        eligible=eligible,
        gated=gated,
        actions=_select_scored_rows(gated, top_n=candidate.top_n),
        thresholds=thresholds,
    )


def _candidate_status(folds: list[CalibrationCandidateFoldResult]) -> str:
    statuses = {item.status for item in folds}
    if "evaluated" in statuses:
        return "evaluated"
    if "no_opinion" in statuses:
        return "no_opinion"
    return "not_evaluated"


def _outcome_metrics(rows: pd.DataFrame) -> tuple[CalibrationOutcomeMetrics, pd.Series]:
    if rows.empty:
        return CalibrationOutcomeMetrics(), pd.Series(dtype="float64")
    gross = pd.to_numeric(rows["target"], errors="coerce")
    cost_multiplier = (
        (1 - CALIBRATION_SLIPPAGE) * (1 - CALIBRATION_FEE)
    ) / ((1 + CALIBRATION_SLIPPAGE) * (1 + CALIBRATION_FEE))
    net = (1.0 + gross) * cost_multiplier - 1.0
    valid = rows.loc[np.isfinite(gross) & np.isfinite(net)].copy()
    if valid.empty:
        return CalibrationOutcomeMetrics(), pd.Series(dtype="float64")
    valid["_gross"] = gross.loc[valid.index]
    valid["_net"] = net.loc[valid.index]
    by_date = valid.groupby("date", sort=True)["_net"].mean()
    return (
        CalibrationOutcomeMetrics(
            signal_market_date_count=len(by_date),
            participant_count=len(valid),
            mean_gross_return=float(valid.groupby("date", sort=True)["_gross"].mean().mean()),
            mean_net_return=float(by_date.mean()),
        ),
        by_date,
    )


def _evaluate_candidate_fold(
    *,
    candidate: CalibrationCandidateManifest,
    fold: MarketDateFold,
    holdout: pd.DataFrame,
    scores: np.ndarray,
    probabilities: np.ndarray | None,
    unavailable_reason: str | None,
    evidence: CalibrationDirectionCalibrationEvidence | None,
) -> CalibrationCandidateFoldResult:
    selection = select_candidate_actions(
        candidate=candidate,
        holdout=holdout,
        scores=scores,
        probabilities=probabilities,
    )
    scored = selection.scored
    eligible = selection.eligible
    gated = selection.gated
    actions = selection.actions
    thresholds = selection.thresholds
    threshold_available = np.isfinite(thresholds)
    reference = _select_scored_rows(eligible, top_n=candidate.top_n)
    reference_outcomes, _ = _outcome_metrics(reference)
    diagnostics = {
        "threshold_unavailable_row_count": int((~threshold_available).sum()),
        "eligible_row_count": len(eligible),
        "eligible_market_date_count": int(eligible["date"].nunique()),
    }
    if unavailable_reason is not None or probabilities is None:
        return CalibrationCandidateFoldResult(
            fold_number=fold.number,
            status="not_evaluated",
            status_reason=unavailable_reason or "Direction Gate is unavailable.",
            **diagnostics,
            eligible_date_reference_baseline_outcomes=reference_outcomes,
            direction_calibration=evidence,
        )
    gate_pass_dates = int(gated["date"].nunique())
    gate_diagnostics = {
        **diagnostics,
        "gate_pass_row_count": len(gated),
        "gate_pass_market_date_count": gate_pass_dates,
        "gate_rejected_market_date_count": diagnostics["eligible_market_date_count"] - gate_pass_dates,
    }
    if actions.empty:
        return CalibrationCandidateFoldResult(
            fold_number=fold.number,
            status="no_opinion",
            **gate_diagnostics,
            eligible_date_reference_baseline_outcomes=reference_outcomes,
            direction_calibration=evidence,
        )
    candidate_outcomes, candidate_by_date = _outcome_metrics(actions)
    matched_baseline = _select_scored_rows(
        eligible.loc[eligible["date"].isin(candidate_by_date.index)], top_n=candidate.top_n
    )
    matched_outcomes, matched_by_date = _outcome_metrics(matched_baseline)
    threshold_hits = actions["target"] >= actions["threshold"]
    aligned_dates = candidate_by_date.index.intersection(matched_by_date.index)
    relative = (
        float((candidate_by_date.loc[aligned_dates] - matched_by_date.loc[aligned_dates]).mean())
        if len(aligned_dates)
        else None
    )
    return CalibrationCandidateFoldResult(
        fold_number=fold.number,
        status="evaluated",
        **gate_diagnostics,
        action_row_count=len(actions),
        action_row_threshold_hit_count=int(threshold_hits.sum()),
        action_row_threshold_hit_rate=float(threshold_hits.groupby(actions["date"]).mean().mean()),
        mean_realized_excess_return=float(
            (actions["target"] - actions["threshold"]).groupby(actions["date"]).mean().mean()
        ),
        candidate_outcomes=candidate_outcomes,
        matched_baseline_outcomes=matched_outcomes,
        eligible_date_reference_baseline_outcomes=reference_outcomes,
        baseline_relative_mean_net_return=relative,
        direction_calibration=evidence,
    )


def _evaluate_model_family(
    model_type: str,
    *,
    frame: pd.DataFrame,
    feature_names: tuple[str, ...],
    folds: list[MarketDateFold],
    candidate_manifest: list[CalibrationCandidateManifest] | None = None,
    prepared_rows: list[_PreparedFoldRows] | None = None,
) -> tuple[CalibrationModelResult, int, int]:
    params = capacity_presets_for(model_type)[CALIBRATION_EXECUTED_PRESET]
    fold_metrics: list[CalibrationFoldMetrics] = []
    evaluated_fold_count = 0
    regression_fit_attempt_count = 0
    direction_gate_fit_attempt_count = 0
    model_unavailable_reason: str | None = None
    empty_fold_count = 0
    candidate_manifest = candidate_manifest or []
    candidate_folds: dict[str, list[CalibrationCandidateFoldResult]] = {
        item.candidate_id: [] for item in candidate_manifest
    }

    prepared_rows = prepared_rows or [
        _prepare_fold_rows(fold, frame) for fold in folds
    ]
    for fold, fold_rows in zip(folds, prepared_rows, strict=True):
        if model_unavailable_reason is not None:
            fold_metrics.append(
                _not_evaluated_fold(
                    fold.number,
                    "Model family unavailable after an earlier fold: "
                    f"{model_unavailable_reason}",
                )
            )
            for candidate in candidate_manifest:
                candidate_folds[candidate.candidate_id].append(
                    CalibrationCandidateFoldResult(
                        fold_number=fold.number,
                        status="not_evaluated",
                        status_reason="Model family unavailable after an earlier fold: "
                        f"{model_unavailable_reason}",
                    )
                )
            continue

        train = fold_rows.train
        holdout = fold_rows.holdout
        if train.empty or holdout.empty:
            empty_fold_count += 1
            fold_metrics.append(
                _not_evaluated_fold(
                    fold.number,
                    "Pooled train or holdout rows are unavailable.",
                )
            )
            for candidate in candidate_manifest:
                candidate_folds[candidate.candidate_id].append(
                    CalibrationCandidateFoldResult(
                        fold_number=fold.number,
                        status="not_evaluated",
                        status_reason="Pooled train or holdout rows are unavailable.",
                    )
                )
            continue

        try:
            regression_fit_attempt_count += 1
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
            model_unavailable_reason = _failure_reason(exc)
            fold_metrics.append(
                _not_evaluated_fold(fold.number, model_unavailable_reason)
            )
            for candidate in candidate_manifest:
                candidate_folds[candidate.candidate_id].append(
                    CalibrationCandidateFoldResult(
                        fold_number=fold.number,
                        status="not_evaluated",
                        status_reason=model_unavailable_reason,
                    )
                )
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
        gate_cache: dict[
            tuple[int, float],
            tuple[np.ndarray | None, str | None, CalibrationDirectionCalibrationEvidence],
        ] = {}
        for candidate in candidate_manifest:
            gate_key = (candidate.volatility_lookback, candidate.multiplier)
            cached = gate_cache.get(gate_key)
            if cached is None:
                direction_gate_fit_attempt_count += 1
                classifier, gate_reason, gate_evidence = _fit_pooled_direction_classifier(
                    train=train,
                    feature_names=feature_names,
                    candidate=candidate,
                    model_type=model_type,
                    model_params=params,
                )
                probabilities: np.ndarray | None = None
                if classifier is not None:
                    try:
                        probabilities = _positive_class_probabilities(
                            classifier,
                            holdout.loc[:, list(feature_names)],
                        )
                    except Exception as exc:
                        logger.exception(
                            "Calibration Direction Gate prediction failed "
                            "model_type=%s fold=%s",
                            model_type,
                            fold.number,
                        )
                        raise CalibrationEvaluationError(
                            "Calibration Direction Gate failed during prediction."
                        ) from exc
                cached = (probabilities, gate_reason, gate_evidence)
                gate_cache[gate_key] = cached
            probabilities, gate_reason, gate_evidence = cached
            candidate_folds[candidate.candidate_id].append(
                _evaluate_candidate_fold(
                    candidate=candidate,
                    fold=fold,
                    holdout=holdout,
                    scores=predicted,
                    probabilities=probabilities,
                    unavailable_reason=gate_reason,
                    evidence=gate_evidence,
                )
            )

    availability_reason = model_unavailable_reason
    if (
        availability_reason is None
        and evaluated_fold_count == 0
        and empty_fold_count == len(folds)
    ):
        availability_reason = "Pooled train or holdout rows are unavailable."
    availability = CalibrationModelAvailability(
        model_type=model_type,
        available=availability_reason is None and evaluated_fold_count > 0,
        reason=availability_reason,
        evaluated_fold_count=evaluated_fold_count,
    )
    return (
        CalibrationModelResult(
            model_type=model_type,
            availability=availability,
            folds=fold_metrics,
            candidate_results=[
                CalibrationCandidateResult(
                    candidate_id=candidate.candidate_id,
                    status=_candidate_status(candidate_folds[candidate.candidate_id]),
                    status_reason=next(
                        (
                            item.status_reason
                            for item in candidate_folds[candidate.candidate_id]
                            if item.status_reason
                        ),
                        None,
                    ),
                    evaluated_fold_count=sum(item.status == "evaluated" for item in candidate_folds[candidate.candidate_id]),
                    no_opinion_fold_count=sum(item.status == "no_opinion" for item in candidate_folds[candidate.candidate_id]),
                    not_evaluated_fold_count=sum(item.status == "not_evaluated" for item in candidate_folds[candidate.candidate_id]),
                    folds=candidate_folds[candidate.candidate_id],
                )
                for candidate in candidate_manifest
            ],
        ),
        regression_fit_attempt_count,
        direction_gate_fit_attempt_count,
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
    try:
        dataset = build_pooled_model_ready_dataset(
            frame,
            feature_config=feature_config,
            shift_map=shift_map,
            return_target=request.return_target,
            horizon_days=request.horizon_days,
            requested_symbols=request.symbols,
            market_dates=market_dates,
            source_priority=CALIBRATION_SOURCE_PRIORITY,
            volatility_lookbacks=CALIBRATION_VOLATILITY_LOOKBACKS,
        )
    except (TypeError, ValueError) as exc:
        raise CalibrationEvaluationError(
            "Calibration dataset could not be prepared."
        ) from exc
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
        for fold, prepared in zip(folds, prepared_fold_rows, strict=True)
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
    regression_fit_attempt_count = 0
    direction_gate_fit_attempt_count = 0
    candidate_manifest = build_calibration_candidate_manifest(
        horizon_days=request.horizon_days
    )
    for model_type in request.model_families:
        result, regression_fits, direction_gate_fits = _evaluate_model_family(
            model_type,
            frame=dataset.frame,
            feature_names=dataset.feature_names,
            folds=folds,
            candidate_manifest=candidate_manifest,
            prepared_rows=prepared_fold_rows,
        )
        model_results.append(result)
        regression_fit_attempt_count += regression_fits
        direction_gate_fit_attempt_count += direction_gate_fits

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
        "candidate_manifest",
        "candidate_fold_summaries",
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
        model_fit_count=regression_fit_attempt_count + direction_gate_fit_attempt_count,
        regression_fit_attempt_count=regression_fit_attempt_count,
        direction_gate_fit_attempt_count=direction_gate_fit_attempt_count,
        deduplicated_market_date_row_count=dataset.deduplicated_row_count,
    )
    evaluation = CalibrationEvaluation(
        status=evaluation_status,
        status_reason=status_reason,
        model_results=model_results,
        candidate_manifest=candidate_manifest,
        candidate_evaluation_policy=CalibrationCandidateEvaluationPolicy(),
        artifact_evidence=CalibrationArtifactEvidence(
            completeness="complete",
            present_artifacts=present_artifacts,
        ),
        resource_evidence=resource_evidence,
    )
    return CalibrationMatrixResponse(
        matrix_id=matrix_id,
        request_id=request_id,
        feature_registry_version=FEATURE_REGISTRY_VERSION,
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

    try:
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
