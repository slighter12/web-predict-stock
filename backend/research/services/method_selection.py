from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.platform.errors import (
    CalibrationBusyError,
    CalibrationEvaluationError,
    DataNotFoundError,
    InsufficientDataError,
)
from backend.platform.time import utc_now
from backend.research.contracts.calibration import (
    CalibrationCandidateFoldResult,
    CalibrationCandidateManifest,
)
from backend.research.contracts.method_selection import (
    MethodCandidateManifest,
    MethodCandidateSummary,
    MethodSelectionComparabilityEvidence,
    MethodSelectionFeatureSetManifest,
    MethodSelectionFoldBoundary,
    MethodSelectionMatrixCreateRequest,
    MethodSelectionMatrixResponse,
    MethodSelectionModelAvailability,
    MethodSelectionOuterFoldResult,
    MethodSelectionResourceEvidence,
)
from backend.research.contracts.runs import FeatureSpec
from backend.research.domain.result_caveats import tw_point_in_time_membership_caveat
from backend.research.policies.calibration import (
    CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
    CALIBRATION_MATCHED_BASELINE_POLICY_VERSION,
    CALIBRATION_SOURCE_PRIORITY,
    CALIBRATION_TOP_N_VALUES,
    CALIBRATION_VOLATILITY_LOOKBACKS,
    CALIBRATION_VOLATILITY_MULTIPLIERS,
    CALIBRATION_VOLATILITY_POLICY_VERSION,
    METHOD_SELECTION_COMPARABILITY_POLICY_VERSION,
    METHOD_SELECTION_FEATURE_ABLATION_POLICY_VERSION,
    METHOD_SELECTION_FINAL_HOLDOUT_DATES,
    METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
    METHOD_SELECTION_FOLD_POLICY_VERSION,
    METHOD_SELECTION_OUTER_STABILITY_POLICY_VERSION,
    METHOD_SELECTION_POLICY_VERSION,
    METHOD_SELECTION_RANKING_POLICY_VERSION,
    METHOD_SELECTION_SCREENING_POLICY_VERSION,
    capacity_presets_for,
)
from backend.research.repositories.method_selection import (
    get_method_selection_matrix_snapshot,
    persist_method_selection_matrix,
)
from backend.research.services import calibration as calibration_service
from backend.research.services.feature_config import build_feature_config
from backend.shared.analytics.features import (
    FEATURE_REGISTRY_VERSION,
    feature_col_name,
    get_feature_definition,
)
from backend.shared.analytics.pooled import (
    MarketDateFold,
    PooledModelReadyDataset,
    build_market_date_folds,
    build_pooled_model_ready_dataset,
)

logger = logging.getLogger(__name__)

_BASELINE_FEATURES = (
    ("ma", 5),
    ("ema", 5),
    ("rsi", 14),
    ("roc", 10),
    ("volatility", 20),
    ("zscore", 20),
)
_ABLATION_FAMILIES = (
    "macd",
    "bbands",
    "atr",
    "stoch",
    "obv",
    "adx_dmi",
    "mfi",
    "cmf",
)
_SCREENING_RECIPE = ("extra_trees", "balanced", 60, 0.75, 10)
_METHOD_SELECTION_ACTIVE = threading.BoundedSemaphore(1)


@dataclass
class _ModelExecutionEvidence:
    evaluated_group_fold_count: int = 0
    unavailable_reasons: list[str] = field(default_factory=list)


@dataclass
class _GroupEvaluation:
    candidate_folds: dict[str, list[CalibrationCandidateFoldResult]]
    model_execution: dict[str, _ModelExecutionEvidence]


def _family_feature_names(family: str) -> list[str]:
    return {
        "macd": ["macd_line", "macd_signal", "macd_histogram"],
        "bbands": ["bbands_upper", "bbands_middle", "bbands_lower"],
        "atr": ["atr"],
        "stoch": ["stoch_k", "stoch_d"],
        "obv": ["obv"],
        "adx_dmi": ["adx", "dmi_plus", "dmi_minus"],
        "mfi": ["mfi"],
        "cmf": ["cmf"],
    }[family]


def _default_specs() -> list[FeatureSpec]:
    specs = [
        FeatureSpec(name=name, window=window, source="close", shift=1)
        for name, window in _BASELINE_FEATURES
    ]
    for family in _ABLATION_FAMILIES:
        for name in _family_feature_names(family):
            definition = get_feature_definition(name)
            if definition is None:
                raise RuntimeError(
                    f"Feature registry lacks required Feature '{name}'."
                )
            specs.append(
                FeatureSpec(
                    name=name,
                    window=int(definition["default_window"]),
                    source="close",
                    shift=1,
                )
            )
    return specs


def build_feature_set_manifests(
) -> tuple[list[MethodSelectionFeatureSetManifest], dict[str, list[FeatureSpec]]]:
    all_specs = _default_specs()
    baseline = all_specs[: len(_BASELINE_FEATURES)]
    additions = all_specs[len(_BASELINE_FEATURES) :]
    definitions: list[tuple[str, list[FeatureSpec], str | None]] = [
        ("baseline", baseline, None),
        *[
            (
                f"baseline_plus_{family}",
                baseline
                + [
                    spec
                    for spec in additions
                    if spec.name in _family_feature_names(family)
                ],
                None,
            )
            for family in _ABLATION_FAMILIES
        ],
        ("full", all_specs, None),
        *[
            (
                f"full_without_{family}",
                baseline
                + [
                    spec
                    for spec in additions
                    if spec.name not in _family_feature_names(family)
                ],
                family,
            )
            for family in _ABLATION_FAMILIES
        ],
    ]
    manifests: list[MethodSelectionFeatureSetManifest] = []
    specs_by_id: dict[str, list[FeatureSpec]] = {}
    for feature_set_id, specs, removed_family in definitions:
        included_families = [
            family
            for family in _ABLATION_FAMILIES
            if any(spec.name in _family_feature_names(family) for spec in specs)
        ]
        manifests.append(
            MethodSelectionFeatureSetManifest(
                feature_set_id=feature_set_id,
                included_feature_families=included_families,
                removed_feature_family=removed_family,
                baseline_feature_names=[spec.name for spec in baseline],
                feature_names=[
                    feature_col_name(spec.name, spec.window, spec.source)
                    for spec in specs
                ],
            )
        )
        specs_by_id[feature_set_id] = specs
    return manifests, specs_by_id


def _manifest(
    phase: str,
    feature_set: MethodSelectionFeatureSetManifest,
    request: MethodSelectionMatrixCreateRequest,
    model_type: str,
    preset: str,
    lookback: int,
    multiplier: float,
    top_n: int,
) -> MethodCandidateManifest:
    candidate_id = (
        f"{phase}_{feature_set.feature_set_id}_{model_type}_{preset}_"
        f"h{request.horizon_days}_l{lookback}_"
        f"m{str(multiplier).replace('.', 'p')}_n{top_n}"
    )
    return MethodCandidateManifest(
        candidate_id=candidate_id,
        phase=phase,
        feature_set_id=feature_set.feature_set_id,
        feature_families=feature_set.included_feature_families,
        horizon_days=request.horizon_days,
        model_type=model_type,
        capacity_preset=preset,
        model_params=capacity_presets_for(model_type)[preset],
        volatility_lookback=lookback,
        multiplier=multiplier,
        top_n=top_n,
        threshold_policy_version=CALIBRATION_VOLATILITY_POLICY_VERSION,
        direction_gate_policy_version=CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
        matched_baseline_policy_version=CALIBRATION_MATCHED_BASELINE_POLICY_VERSION,
    )


def build_screening_candidate_manifests(
    request: MethodSelectionMatrixCreateRequest,
    feature_sets: list[MethodSelectionFeatureSetManifest],
) -> list[MethodCandidateManifest]:
    return [
        _manifest("feature_screening", feature_set, request, *_SCREENING_RECIPE)
        for feature_set in feature_sets
    ]


def build_tuning_candidate_manifests(
    request: MethodSelectionMatrixCreateRequest,
    feature_set: MethodSelectionFeatureSetManifest,
) -> list[MethodCandidateManifest]:
    return [
        _manifest(
            "parameter_search",
            feature_set,
            request,
            model_type,
            preset,
            lookback,
            multiplier,
            top_n,
        )
        for model_type, preset, lookback, multiplier, top_n in product(
            request.model_families,
            ("conservative", "balanced", "flexible"),
            CALIBRATION_VOLATILITY_LOOKBACKS,
            CALIBRATION_VOLATILITY_MULTIPLIERS,
            CALIBRATION_TOP_N_VALUES,
        )
    ]


def _as_calibration_candidate(
    manifest: MethodCandidateManifest,
) -> CalibrationCandidateManifest:
    return CalibrationCandidateManifest(
        candidate_id=manifest.candidate_id,
        horizon_days=manifest.horizon_days,
        volatility_lookback=manifest.volatility_lookback,
        multiplier=manifest.multiplier,
        top_n=manifest.top_n,
    )


def _boundary(
    fold: MarketDateFold,
    frame: pd.DataFrame,
) -> MethodSelectionFoldBoundary:
    rows = calibration_service._prepare_fold_rows(fold, frame)
    train_start, train_end = calibration_service._date_bounds(fold.train_dates)
    purge_start, purge_end = calibration_service._date_bounds(fold.purge_dates)
    holdout_start, holdout_end = calibration_service._date_bounds(fold.holdout_dates)
    return MethodSelectionFoldBoundary(
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
        train_row_count=len(rows.train),
        target_purge_row_count=len(rows.raw_train) - len(rows.train),
        holdout_row_count=len(rows.holdout),
    )


def _summary(
    candidate_id: str,
    folds: list[CalibrationCandidateFoldResult],
) -> MethodCandidateSummary:
    if any(item.status == "not_evaluated" for item in folds):
        reason = next(
            (
                item.status_reason
                for item in folds
                if item.status == "not_evaluated" and item.status_reason
            ),
            "A Fold was not evaluated.",
        )
        return MethodCandidateSummary(
            candidate_id=candidate_id,
            status="not_evaluated",
            fold_results=folds,
            status_reason=reason,
            rejection_reason=reason,
        )
    if any(item.status == "no_opinion" for item in folds):
        return MethodCandidateSummary(
            candidate_id=candidate_id,
            status="no_opinion",
            fold_results=folds,
            rejection_reason="At least one Fold produced no Action Rows.",
        )
    action_count = sum(item.action_row_count for item in folds)
    hit_count = sum(item.action_row_threshold_hit_count for item in folds)
    excess_returns = [
        item.mean_realized_excess_return
        for item in folds
        if item.mean_realized_excess_return is not None
    ]
    baseline_relative_returns = [
        item.baseline_relative_mean_net_return
        for item in folds
        if item.baseline_relative_mean_net_return is not None
    ]
    return MethodCandidateSummary(
        candidate_id=candidate_id,
        status="evaluated",
        fold_results=folds,
        action_row_count=action_count,
        action_row_threshold_hit_count=hit_count,
        action_row_threshold_hit_rate=(hit_count / action_count if action_count else None),
        mean_realized_excess_return=(
            float(np.mean(excess_returns)) if excess_returns else None
        ),
        baseline_relative_mean_net_return=(
            float(np.mean(baseline_relative_returns))
            if baseline_relative_returns
            else None
        ),
    )


def _rank(
    summaries: list[MethodCandidateSummary],
    *,
    outer: bool,
) -> list[MethodCandidateSummary]:
    def evidence_key(summary: MethodCandidateSummary) -> tuple[float, ...]:
        values = [
            summary.action_row_threshold_hit_rate,
            summary.mean_realized_excess_return,
        ]
        if outer:
            values.append(summary.action_row_stability)
        values.append(summary.baseline_relative_mean_net_return)
        return tuple(-(value if value is not None else -math.inf) for value in values)

    evaluated = [item for item in summaries if item.status == "evaluated"]
    remaining = [item for item in summaries if item.status != "evaluated"]
    ordered = sorted(
        evaluated,
        key=lambda item: (evidence_key(item), item.candidate_id),
    ) + sorted(remaining, key=lambda item: item.candidate_id)
    ranked: list[MethodCandidateSummary] = []
    for rank, summary in enumerate(ordered, start=1):
        tied_candidate_ids = sorted(
            item.candidate_id
            for item in evaluated
            if evidence_key(item) == evidence_key(summary)
        )
        rejection_reason = summary.rejection_reason
        if summary.status == "evaluated" and rank > 1:
            rejection_reason = "Lower ranked under the recorded selection hierarchy."
        ranked.append(
            summary.model_copy(
                update={
                    "rank": rank,
                    "rejection_reason": rejection_reason,
                    "semantic_tie": len(tied_candidate_ids) > 1,
                    "tied_candidate_ids": (
                        tied_candidate_ids if len(tied_candidate_ids) > 1 else []
                    ),
                    "deterministic_tie_break": (
                        "candidate_id" if len(tied_candidate_ids) > 1 else None
                    ),
                }
            )
        )
    return ranked


def _evaluate_group(
    manifests: list[MethodCandidateManifest],
    frame: pd.DataFrame,
    feature_names_by_set: dict[str, tuple[str, ...]],
    folds: list[MarketDateFold],
    fit_counts: dict[str, int],
) -> _GroupEvaluation:
    candidate_folds = {manifest.candidate_id: [] for manifest in manifests}
    groups: dict[tuple[str, str, str], list[MethodCandidateManifest]] = defaultdict(list)
    model_execution: dict[str, _ModelExecutionEvidence] = defaultdict(
        _ModelExecutionEvidence
    )
    for manifest in manifests:
        groups[
            (manifest.feature_set_id, manifest.model_type, manifest.capacity_preset)
        ].append(manifest)
    prepared_rows = [
        calibration_service._prepare_fold_rows(fold, frame) for fold in folds
    ]
    for (feature_set_id, model_type, _preset), group in groups.items():
        unavailable_reason: str | None = None
        feature_names = feature_names_by_set[feature_set_id]
        for fold, rows in zip(folds, prepared_rows, strict=True):
            if unavailable_reason or rows.train.empty or rows.holdout.empty:
                reason = unavailable_reason or "Pooled train or holdout rows are unavailable."
                for manifest in group:
                    candidate_folds[manifest.candidate_id].append(
                        CalibrationCandidateFoldResult(
                            fold_number=fold.number,
                            status="not_evaluated",
                            status_reason=reason,
                        )
                    )
                continue
            try:
                fit_counts["regression"] += 1
                model = calibration_service.model_service.fit_regressor(
                    model_type=model_type,
                    X_train=rows.train.loc[:, list(feature_names)],
                    y_train=rows.train["target"],
                    model_params=group[0].model_params,
                )
                scores = np.asarray(
                    model.predict(rows.holdout.loc[:, list(feature_names)])
                ).reshape(-1)
                if len(scores) != len(rows.holdout) or not np.isfinite(scores).all():
                    raise ValueError("model produced a non-finite or misaligned prediction")
            except calibration_service.ModelUnavailableError as exc:
                unavailable_reason = calibration_service._failure_reason(exc)
                model_execution[model_type].unavailable_reasons.append(
                    unavailable_reason
                )
                for manifest in group:
                    candidate_folds[manifest.candidate_id].append(
                        CalibrationCandidateFoldResult(
                            fold_number=fold.number,
                            status="not_evaluated",
                            status_reason=unavailable_reason,
                        )
                    )
                continue
            except Exception as exc:
                logger.exception(
                    "Method Selection regression failed model_type=%s fold=%s",
                    model_type,
                    fold.number,
                )
                raise CalibrationEvaluationError(
                    "Method Selection regression failed during evaluation."
                ) from exc
            model_execution[model_type].evaluated_group_fold_count += 1
            gate_cache: dict[tuple[int, float], tuple[np.ndarray | None, str | None, Any]] = {}
            for manifest in group:
                gate_key = (manifest.volatility_lookback, manifest.multiplier)
                if gate_key not in gate_cache:
                    try:
                        fit_counts["gate"] += 1
                        classifier, reason, evidence = (
                            calibration_service._fit_pooled_direction_classifier(
                                train=rows.train,
                                feature_names=feature_names,
                                candidate=_as_calibration_candidate(manifest),
                                model_type=model_type,
                                model_params=manifest.model_params,
                            )
                        )
                        probabilities = (
                            None
                            if classifier is None
                            else np.asarray(
                                classifier.predict_proba(
                                    rows.holdout.loc[:, list(feature_names)]
                                )
                            )[:, 1]
                        )
                        if probabilities is not None and (
                            len(probabilities) != len(rows.holdout)
                            or not np.isfinite(probabilities).all()
                        ):
                            raise ValueError(
                                "Direction Gate produced invalid probabilities."
                            )
                        gate_cache[gate_key] = probabilities, reason, evidence
                    except Exception as exc:
                        logger.exception(
                            "Method Selection Direction Gate failed model_type=%s fold=%s",
                            model_type,
                            fold.number,
                        )
                        raise CalibrationEvaluationError(
                            "Method Selection Direction Gate failed during evaluation."
                        ) from exc
                probabilities, reason, evidence = gate_cache[gate_key]
                candidate_folds[manifest.candidate_id].append(
                    calibration_service._evaluate_candidate_fold(
                        candidate=_as_calibration_candidate(manifest),
                        fold=fold,
                        holdout=rows.holdout,
                        scores=scores,
                        probabilities=probabilities,
                        unavailable_reason=reason,
                        evidence=evidence,
                    )
                )
    return _GroupEvaluation(candidate_folds, model_execution)


def _load_dataset(
    request: MethodSelectionMatrixCreateRequest,
    specs: list[FeatureSpec],
    feature_names_by_set: dict[str, tuple[str, ...]],
) -> tuple[PooledModelReadyDataset, tuple, tuple]:
    calibration_request = calibration_service.CalibrationMatrixCreateRequest(
        market=request.market,
        symbols=request.symbols,
        date_range=request.date_range,
        horizon_days=request.horizon_days,
        features=specs[: len(_BASELINE_FEATURES)],
        model_families=request.model_families,
    )
    raw, market_dates = calibration_service._load_market_frame(calibration_request)
    if raw.empty:
        raise DataNotFoundError(
            "No market data found for the requested symbols and date range."
        )
    if len(market_dates) <= METHOD_SELECTION_FINAL_HOLDOUT_DATES:
        raise InsufficientDataError(
            "Not enough Market Dates after reserving the final Holdout."
        )
    selection_dates = market_dates[:-METHOD_SELECTION_FINAL_HOLDOUT_DATES]
    final_holdout_dates = market_dates[-METHOD_SELECTION_FINAL_HOLDOUT_DATES:]
    feature_config, shift_map = build_feature_config(specs)
    volatility_columns = tuple(
        f"open_to_open_volatility_{lookback}"
        for lookback in CALIBRATION_VOLATILITY_LOOKBACKS
    )
    dataset = build_pooled_model_ready_dataset(
        raw,
        feature_config=feature_config,
        shift_map=shift_map,
        return_target="open_to_open",
        horizon_days=request.horizon_days,
        requested_symbols=request.symbols,
        market_dates=selection_dates,
        source_priority=CALIBRATION_SOURCE_PRIORITY,
        volatility_lookbacks=CALIBRATION_VOLATILITY_LOOKBACKS,
        complete_case_extra_columns=volatility_columns,
        counterfactual_feature_sets=feature_names_by_set,
    )
    if dataset.frame.empty:
        raise InsufficientDataError(
            "Method Selection Matrix has no common Model-Ready Universe rows."
        )
    return dataset, selection_dates, final_holdout_dates


def _merge_model_execution(
    destination: dict[str, _ModelExecutionEvidence],
    source: dict[str, _ModelExecutionEvidence],
) -> None:
    for model_type, evidence in source.items():
        target = destination.setdefault(model_type, _ModelExecutionEvidence())
        target.evaluated_group_fold_count += evidence.evaluated_group_fold_count
        target.unavailable_reasons.extend(evidence.unavailable_reasons)


def _availability(
    manifests: list[MethodCandidateManifest],
    execution: dict[str, _ModelExecutionEvidence],
) -> list[MethodSelectionModelAvailability]:
    availability: list[MethodSelectionModelAvailability] = []
    for model_type in sorted({manifest.model_type for manifest in manifests}):
        evidence = execution.get(model_type, _ModelExecutionEvidence())
        available = evidence.evaluated_group_fold_count > 0
        availability.append(
            MethodSelectionModelAvailability(
                model_type=model_type,
                available=available,
                reason=(
                    None
                    if available
                    else next(iter(evidence.unavailable_reasons), None)
                ),
                evaluated_group_fold_count=evidence.evaluated_group_fold_count,
            )
        )
    return availability


def _maximum_fit_counts(
    request: MethodSelectionMatrixCreateRequest,
    *,
    phase_a_count: int,
    outer_fold_count: int,
) -> tuple[int, int]:
    inner_fold_count = 3
    parameter_groups = len(request.model_families) * 3
    maximum_regression = (
        phase_a_count * outer_fold_count * inner_fold_count
        + parameter_groups * outer_fold_count * inner_fold_count
        + outer_fold_count
    )
    maximum_gates = (
        phase_a_count * outer_fold_count * inner_fold_count
        + parameter_groups * 9 * outer_fold_count * inner_fold_count
        + outer_fold_count
    )
    return maximum_regression, maximum_gates


def _create_method_selection_matrix(
    request: MethodSelectionMatrixCreateRequest,
    *,
    request_id: str,
    matrix_id: str | None = None,
) -> MethodSelectionMatrixResponse:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    feature_sets, specs_by_id = build_feature_set_manifests()
    feature_names_by_set = {
        feature_set_id: tuple(
            feature_col_name(spec.name, spec.window, spec.source)
            for spec in specs
        )
        for feature_set_id, specs in specs_by_id.items()
    }
    phase_a_manifests = build_screening_candidate_manifests(request, feature_sets)
    dataset, selection_dates, final_holdout_dates = _load_dataset(
        request,
        _default_specs(),
        feature_names_by_set,
    )
    model_ready_dates = tuple(sorted(set(dataset.frame["date"])))
    try:
        outer_folds = build_market_date_folds(
            model_ready_dates,
            splits=5,
            test_size=0.1,
            purge=request.horizon_days,
        )
    except ValueError as exc:
        raise InsufficientDataError(
            "Common Model-Ready Market Date axis cannot form five outer Folds: "
            f"{exc}"
        ) from exc

    fit_counts: dict[str, int] = defaultdict(int)
    records: list[MethodSelectionOuterFoldResult] = []
    phase_b_by_id: dict[str, MethodCandidateManifest] = {}
    outer_results_by_candidate: dict[
        str, list[CalibrationCandidateFoldResult]
    ] = defaultdict(list)
    model_execution: dict[str, _ModelExecutionEvidence] = {}

    for outer_fold in outer_folds:
        try:
            inner_folds = build_market_date_folds(
                outer_fold.train_dates,
                splits=3,
                test_size=0.2,
                purge=request.horizon_days,
            )
        except ValueError as exc:
            raise InsufficientDataError(
                "Common Model-Ready Market Date axis in Outer Fold "
                f"{outer_fold.number} cannot form three inner Folds: {exc}"
            ) from exc

        phase_a_evaluation = _evaluate_group(
            phase_a_manifests,
            dataset.frame,
            feature_names_by_set,
            inner_folds,
            fit_counts,
        )
        _merge_model_execution(model_execution, phase_a_evaluation.model_execution)
        phase_a_summaries = _rank(
            [
                _summary(
                    manifest.candidate_id,
                    phase_a_evaluation.candidate_folds[manifest.candidate_id],
                )
                for manifest in phase_a_manifests
            ],
            outer=False,
        )
        phase_a_winner = next(
            (summary for summary in phase_a_summaries if summary.status == "evaluated"),
            None,
        )
        phase_b_summaries: list[MethodCandidateSummary] = []
        phase_b_winner: MethodCandidateSummary | None = None
        outer_result: CalibrationCandidateFoldResult | None = None

        if phase_a_winner is not None:
            selected_feature_set_id = next(
                manifest.feature_set_id
                for manifest in phase_a_manifests
                if manifest.candidate_id == phase_a_winner.candidate_id
            )
            selected_feature_set = next(
                item
                for item in feature_sets
                if item.feature_set_id == selected_feature_set_id
            )
            phase_b_manifests = build_tuning_candidate_manifests(
                request,
                selected_feature_set,
            )
            phase_b_by_id.update(
                {manifest.candidate_id: manifest for manifest in phase_b_manifests}
            )
            phase_b_evaluation = _evaluate_group(
                phase_b_manifests,
                dataset.frame,
                feature_names_by_set,
                inner_folds,
                fit_counts,
            )
            _merge_model_execution(
                model_execution,
                phase_b_evaluation.model_execution,
            )
            phase_b_summaries = _rank(
                [
                    _summary(
                        manifest.candidate_id,
                        phase_b_evaluation.candidate_folds[manifest.candidate_id],
                    )
                    for manifest in phase_b_manifests
                ],
                outer=False,
            )
            phase_b_winner = next(
                (
                    summary
                    for summary in phase_b_summaries
                    if summary.status == "evaluated"
                ),
                None,
            )
            if phase_b_winner is not None:
                selected_manifest = phase_b_by_id[phase_b_winner.candidate_id]
                outer_evaluation = _evaluate_group(
                    [selected_manifest],
                    dataset.frame,
                    feature_names_by_set,
                    [outer_fold],
                    fit_counts,
                )
                _merge_model_execution(
                    model_execution,
                    outer_evaluation.model_execution,
                )
                outer_result = outer_evaluation.candidate_folds[
                    selected_manifest.candidate_id
                ][0]
                outer_results_by_candidate[selected_manifest.candidate_id].append(
                    outer_result
                )

        records.append(
            MethodSelectionOuterFoldResult(
                outer_fold=_boundary(outer_fold, dataset.frame),
                inner_folds=[
                    _boundary(inner_fold, dataset.frame)
                    for inner_fold in inner_folds
                ],
                phase_a_summaries=phase_a_summaries,
                phase_a_selected_candidate_id=(
                    phase_a_winner.candidate_id if phase_a_winner else None
                ),
                phase_b_summaries=phase_b_summaries,
                selected_candidate_id=(
                    phase_b_winner.candidate_id if phase_b_winner else None
                ),
                selection_reason=(
                    "Highest ranked complete Phase B inner-Fold candidate."
                    if phase_b_winner
                    else "No inner candidate produced complete Action Row evidence."
                ),
                outer_result=outer_result,
            )
        )

    outer_summaries: list[MethodCandidateSummary] = []
    for candidate_id, candidate_folds in outer_results_by_candidate.items():
        summary = _summary(candidate_id, candidate_folds)
        hit_rates = [
            fold.action_row_threshold_hit_rate
            for fold in candidate_folds
            if fold.action_row_threshold_hit_rate is not None
        ]
        stability = (
            1.0 - float(np.std(hit_rates)) if len(hit_rates) >= 2 else None
        )
        outer_summaries.append(
            summary.model_copy(update={"action_row_stability": stability})
        )

    maximum_regression, maximum_gates = _maximum_fit_counts(
        request,
        phase_a_count=len(phase_a_manifests),
        outer_fold_count=len(outer_folds),
    )
    caveat_payload = tw_point_in_time_membership_caveat(
        market=request.market,
        request_payload=request.model_dump(mode="json"),
    )
    complete_case_counts = dict(dataset.counterfactual_complete_case_row_counts)
    common_row_count = len(dataset.frame)
    comparability_evidence = MethodSelectionComparabilityEvidence(
        policy_version=METHOD_SELECTION_COMPARABILITY_POLICY_VERSION,
        selection_market_date_count=len(selection_dates),
        common_market_date_count=len(model_ready_dates),
        common_row_count=common_row_count,
        feature_set_complete_case_row_counts=complete_case_counts,
        common_policy_rows_lost_by_feature_set={
            feature_set_id: max(count - common_row_count, 0)
            for feature_set_id, count in complete_case_counts.items()
        },
    )
    resource_evidence = MethodSelectionResourceEvidence(
        wall_clock_seconds=max(time.perf_counter() - started_wall, 0.0),
        cpu_seconds=max(time.process_time() - started_cpu, 0.0),
        peak_rss_bytes=calibration_service._peak_rss_bytes(),
        model_ready_row_count=common_row_count,
        feature_count=len(dataset.feature_names),
        fold_count=len(outer_folds),
        model_fit_count=fit_counts["regression"] + fit_counts["gate"],
        regression_fit_attempt_count=fit_counts["regression"],
        direction_gate_fit_attempt_count=fit_counts["gate"],
        deduplicated_market_date_row_count=dataset.deduplicated_row_count,
        maximum_regression_fit_count=maximum_regression,
        maximum_direction_gate_fit_count=maximum_gates,
    )
    calibration_request = calibration_service.CalibrationMatrixCreateRequest(
        market=request.market,
        symbols=request.symbols,
        date_range=request.date_range,
        horizon_days=request.horizon_days,
        features=_default_specs()[: len(_BASELINE_FEATURES)],
        model_families=request.model_families,
    )
    response = MethodSelectionMatrixResponse(
        matrix_id=matrix_id or f"method_selection_{uuid4().hex}",
        request_id=request_id,
        request=request,
        feature_registry_version=FEATURE_REGISTRY_VERSION,
        dataset=calibration_service._dataset_summary(calibration_request, dataset),
        final_holdout_policy_version=METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
        final_holdout_market_dates=list(final_holdout_dates),
        fold_policy_version=METHOD_SELECTION_FOLD_POLICY_VERSION,
        policy_version=METHOD_SELECTION_POLICY_VERSION,
        feature_ablation_policy_version=METHOD_SELECTION_FEATURE_ABLATION_POLICY_VERSION,
        ranking_policy_version=METHOD_SELECTION_RANKING_POLICY_VERSION,
        screening_policy_version=METHOD_SELECTION_SCREENING_POLICY_VERSION,
        outer_stability_policy_version=METHOD_SELECTION_OUTER_STABILITY_POLICY_VERSION,
        feature_sets=feature_sets,
        phase_a_candidate_manifests=phase_a_manifests,
        phase_b_candidate_manifests=list(phase_b_by_id.values()),
        outer_folds=records,
        outer_candidate_summaries=_rank(outer_summaries, outer=True),
        comparison_caveats=[caveat_payload] if caveat_payload else [],
        resource_evidence=resource_evidence,
        model_availability=_availability(
            phase_a_manifests + list(phase_b_by_id.values()),
            model_execution,
        ),
        comparability_evidence=comparability_evidence,
        created_at=utc_now(),
    )
    persist_method_selection_matrix(response.model_dump(mode="json"))
    return response


def create_method_selection_matrix(
    request: MethodSelectionMatrixCreateRequest,
    *,
    request_id: str,
    matrix_id: str | None = None,
) -> MethodSelectionMatrixResponse:
    if not _METHOD_SELECTION_ACTIVE.acquire(blocking=False):
        raise CalibrationBusyError(
            "Another Method Selection Matrix is already running; retry later."
        )
    try:
        return _create_method_selection_matrix(
            request,
            request_id=request_id,
            matrix_id=matrix_id,
        )
    finally:
        _METHOD_SELECTION_ACTIVE.release()


def get_method_selection_matrix(matrix_id: str) -> MethodSelectionMatrixResponse:
    return MethodSelectionMatrixResponse.model_validate(
        get_method_selection_matrix_snapshot(matrix_id)
    )
