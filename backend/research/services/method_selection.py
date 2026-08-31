from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
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
    MethodSelectionFinalHoldoutResult,
    MethodSelectionFoldBoundary,
    MethodSelectionMatrixCreateRequest,
    MethodSelectionMatrixResponse,
    MethodSelectionModelAvailability,
    MethodSelectionOuterFoldResult,
    MethodSelectionResourceEvidence,
)
from backend.research.contracts.runs import (
    ExecutionConfig,
    FeatureSpec,
    ResearchRunCreateRequest,
    ResearchRunResponse,
)
from backend.research.domain.result_caveats import tw_point_in_time_membership_caveat
from backend.research.policies.calibration import (
    CALIBRATION_DIRECTION_GATE_POLICY_VERSION,
    CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION,
    CALIBRATION_MATCHED_BASELINE_POLICY_VERSION,
    CALIBRATION_SOURCE_PRIORITY,
    CALIBRATION_TOP_N_VALUES,
    CALIBRATION_VOLATILITY_LOOKBACKS,
    CALIBRATION_VOLATILITY_MULTIPLIERS,
    CALIBRATION_VOLATILITY_POLICY_VERSION,
    METHOD_SELECTION_COMPARABILITY_POLICY_VERSION,
    METHOD_SELECTION_FEATURE_ABLATION_POLICY_VERSION,
    METHOD_SELECTION_FINAL_HOLDOUT_DATES,
    METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION,
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
    persist_method_selection_batch,
)
from backend.research.services import calibration as calibration_service
from backend.research.services.execution import build_regression_diagnostics
from backend.research.services.feature_config import build_feature_config
from backend.research.services.registry import (
    build_success_registry_payload,
    record_started,
    record_success,
)
from backend.research.services.run_projection import project_live_response
from backend.research.services.tradability import EXECUTION_COST_MODEL_VERSION
from backend.research.domain.version_pack import build_version_pack_payload
from backend.shared.analytics import backtest as backtest_service
from backend.shared.analytics.features import (
    FEATURE_REGISTRY_VERSION,
    feature_col_name,
    get_feature_definition,
)
from backend.shared.analytics.models import MISSING_FEATURE_POLICY_VERSION
from backend.shared.analytics.pooled import (
    MarketDateFold,
    PooledModelReadyDataset,
    build_market_date_folds,
    build_pooled_model_ready_dataset,
)
from backend.shared.analytics.strategy import (
    ADOPTION_COMPARISON_POLICY_VERSION,
    BOOTSTRAP_POLICY_VERSION,
    COMPARISON_REVIEW_MATRIX_VERSION,
    IC_OVERLAP_POLICY_VERSION,
    RESEARCH_ONLY_COMPARABLE,
    SCHEDULED_REVIEW_CADENCE,
    build_price_basis_version,
)
from backend.shared.contracts.common import ACTIVE_TRADABILITY_CONTRACT_VERSION

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


@dataclass(frozen=True)
class _MethodSelectionDatasets:
    selection: PooledModelReadyDataset
    full: PooledModelReadyDataset
    selection_dates: tuple[date, ...]
    final_holdout_dates: tuple[date, ...]
    final_holdout_maturity_date: date | None = None
    final_holdout_maturity_buffer_market_date_count: int = 0


@dataclass(frozen=True)
class _MethodSelectionInputs:
    raw: pd.DataFrame
    full_market_dates: tuple[date, ...]
    selection_dates: tuple[date, ...]
    final_holdout_dates: tuple[date, ...]
    final_holdout_maturity_date: date
    final_holdout_maturity_buffer_market_date_count: int


@dataclass(frozen=True)
class _FinalCandidateArtifacts:
    manifest: MethodCandidateManifest
    fold: MarketDateFold
    prepared_rows: Any
    model: Any | None
    scores: np.ndarray | None
    probabilities: np.ndarray | None
    direction_evidence: Any | None
    fold_result: CalibrationCandidateFoldResult


@dataclass
class _PreparedPromotedRun:
    run_id: str
    request: ResearchRunCreateRequest
    runtime_context: dict[str, Any]
    response: ResearchRunResponse
    registry_payload: dict[str, Any]
    computation_mode: str = "computed"


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
                            else calibration_service._positive_class_probabilities(
                                classifier,
                                rows.holdout.loc[:, list(feature_names)],
                            )
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


def _load_method_selection_inputs(
    request: MethodSelectionMatrixCreateRequest,
    specs: list[FeatureSpec],
) -> _MethodSelectionInputs:
    calibration_request = calibration_service.CalibrationMatrixCreateRequest(
        market=request.market,
        symbols=request.symbols,
        date_range=request.date_range,
        horizon_days=request.horizon_days,
        features=specs[: len(_BASELINE_FEATURES)],
        model_families=request.model_families,
    )
    maturity_query_end = request.date_range.end + timedelta(
        days=max(90, request.horizon_days * 10)
    )
    raw, market_dates = calibration_service._load_market_frame(
        calibration_request,
        request.date_range.start,
        maturity_query_end,
    )
    if raw.empty:
        raise DataNotFoundError(
            "No market data found for the requested symbols and date range."
        )
    market_dates = tuple(sorted(set(market_dates)))
    requested_market_dates = tuple(
        item for item in market_dates if item <= request.date_range.end
    )
    maturity_buffer_dates = tuple(
        item for item in market_dates if item > request.date_range.end
    )
    if len(maturity_buffer_dates) < request.horizon_days:
        raise InsufficientDataError(
            "Not enough official Market Dates after the requested end date to mature "
            f"the {request.horizon_days}-day open-to-open Final Holdout "
            f"({METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION})."
        )
    if len(requested_market_dates) <= METHOD_SELECTION_FINAL_HOLDOUT_DATES:
        raise InsufficientDataError(
            "Not enough Market Dates after reserving the final Holdout."
        )
    selection_dates = requested_market_dates[:-METHOD_SELECTION_FINAL_HOLDOUT_DATES]
    final_holdout_dates = requested_market_dates[-METHOD_SELECTION_FINAL_HOLDOUT_DATES:]
    return _MethodSelectionInputs(
        raw=raw,
        full_market_dates=market_dates,
        selection_dates=selection_dates,
        final_holdout_dates=final_holdout_dates,
        final_holdout_maturity_date=maturity_buffer_dates[request.horizon_days - 1],
        final_holdout_maturity_buffer_market_date_count=len(maturity_buffer_dates),
    )


def _build_method_selection_dataset(
    request: MethodSelectionMatrixCreateRequest,
    raw: pd.DataFrame,
    specs: list[FeatureSpec],
    feature_names_by_set: dict[str, tuple[str, ...]],
    market_dates: tuple[date, ...],
) -> PooledModelReadyDataset:
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
        market_dates=market_dates,
        source_priority=CALIBRATION_SOURCE_PRIORITY,
        volatility_lookbacks=CALIBRATION_VOLATILITY_LOOKBACKS,
        complete_case_extra_columns=volatility_columns,
        counterfactual_feature_sets=feature_names_by_set,
    )
    return dataset


def _load_method_selection_datasets(
    request: MethodSelectionMatrixCreateRequest,
    specs: list[FeatureSpec],
    feature_names_by_set: dict[str, tuple[str, ...]],
) -> _MethodSelectionDatasets:
    inputs = _load_method_selection_inputs(request, specs)
    selection = _build_method_selection_dataset(
        request,
        inputs.raw,
        specs,
        feature_names_by_set,
        inputs.selection_dates,
    )
    full = _build_method_selection_dataset(
        request,
        inputs.raw,
        specs,
        feature_names_by_set,
        inputs.full_market_dates,
    )
    if selection.frame.empty:
        raise InsufficientDataError(
            "Method Selection Matrix has no common Model-Ready Universe rows."
        )
    if full.frame.empty:
        raise InsufficientDataError(
            "Method Selection Matrix has no complete Final Holdout rows."
        )
    return _MethodSelectionDatasets(
        selection=selection,
        full=full,
        selection_dates=inputs.selection_dates,
        final_holdout_dates=inputs.final_holdout_dates,
        final_holdout_maturity_date=inputs.final_holdout_maturity_date,
        final_holdout_maturity_buffer_market_date_count=(
            inputs.final_holdout_maturity_buffer_market_date_count
        ),
    )


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


def _final_holdout_fold(
    selection_dates: tuple[date, ...],
    final_holdout_dates: tuple[date, ...],
    horizon_days: int,
) -> MarketDateFold:
    if len(selection_dates) <= horizon_days:
        raise InsufficientDataError(
            "Not enough pre-final Market Dates remain after the final purge."
        )
    return MarketDateFold(
        number=6,
        train_dates=selection_dates[:-horizon_days],
        purge_dates=selection_dates[-horizon_days:],
        holdout_dates=final_holdout_dates,
    )


def _evaluate_final_candidate(
    manifest: MethodCandidateManifest,
    frame: pd.DataFrame,
    feature_names_by_set: dict[str, tuple[str, ...]],
    fold: MarketDateFold,
    fit_counts: dict[str, int],
) -> _FinalCandidateArtifacts:
    rows = calibration_service._prepare_fold_rows(fold, frame)
    if rows.train.empty or rows.holdout.empty:
        return _FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=rows,
            model=None,
            scores=None,
            probabilities=None,
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="not_evaluated",
                status_reason="Pooled pre-final train or Final Holdout rows are unavailable.",
            ),
        )

    feature_names = feature_names_by_set[manifest.feature_set_id]
    try:
        fit_counts["regression"] += 1
        model = calibration_service.model_service.fit_regressor(
            model_type=manifest.model_type,
            X_train=rows.train.loc[:, list(feature_names)],
            y_train=rows.train["target"],
            model_params=manifest.model_params,
        )
        scores = np.asarray(
            model.predict(rows.holdout.loc[:, list(feature_names)])
        ).reshape(-1)
        if len(scores) != len(rows.holdout) or not np.isfinite(scores).all():
            raise ValueError("model produced a non-finite or misaligned prediction")
    except calibration_service.ModelUnavailableError as exc:
        reason = calibration_service._failure_reason(exc)
        return _FinalCandidateArtifacts(
            manifest=manifest,
            fold=fold,
            prepared_rows=rows,
            model=None,
            scores=None,
            probabilities=None,
            direction_evidence=None,
            fold_result=CalibrationCandidateFoldResult(
                fold_number=fold.number,
                status="not_evaluated",
                status_reason=reason,
            ),
        )
    except Exception as exc:
        logger.exception(
            "Final Holdout regression failed model_type=%s candidate=%s",
            manifest.model_type,
            manifest.candidate_id,
        )
        raise CalibrationEvaluationError(
            "Final Holdout regression failed during evaluation."
        ) from exc

    try:
        fit_counts["gate"] += 1
        classifier, gate_reason, gate_evidence = (
            calibration_service._fit_pooled_direction_classifier(
                train=rows.train,
                feature_names=feature_names,
                candidate=_as_calibration_candidate(manifest),
                model_type=manifest.model_type,
                model_params=manifest.model_params,
            )
        )
        probabilities = (
            None
            if classifier is None
            else calibration_service._positive_class_probabilities(
                classifier,
                rows.holdout.loc[:, list(feature_names)],
            )
        )
    except Exception as exc:
        logger.exception(
            "Final Holdout Direction Gate failed model_type=%s candidate=%s",
            manifest.model_type,
            manifest.candidate_id,
        )
        raise CalibrationEvaluationError(
            "Final Holdout Direction Gate failed during evaluation."
        ) from exc

    fold_result = calibration_service._evaluate_candidate_fold(
        candidate=_as_calibration_candidate(manifest),
        fold=fold,
        holdout=rows.holdout,
        scores=scores,
        probabilities=probabilities,
        unavailable_reason=gate_reason,
        evidence=gate_evidence,
    )
    return _FinalCandidateArtifacts(
        manifest=manifest,
        fold=fold,
        prepared_rows=rows,
        model=model,
        scores=scores,
        probabilities=probabilities,
        direction_evidence=gate_evidence,
        fold_result=fold_result,
    )


def _final_action_rows(
    artifacts: _FinalCandidateArtifacts,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if artifacts.scores is None or artifacts.probabilities is None:
        return pd.DataFrame(), pd.DataFrame()
    selection = calibration_service.select_candidate_actions(
        candidate=_as_calibration_candidate(artifacts.manifest),
        holdout=artifacts.prepared_rows.holdout,
        scores=artifacts.scores,
        probabilities=artifacts.probabilities,
    )
    return selection.actions, selection.scored


def _pivot_holdout_values(
    frame: pd.DataFrame,
    column: str,
    *,
    index: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    values = frame.pivot(index="date", columns="symbol", values=column)
    values.index = pd.to_datetime(values.index)
    return values.reindex(index=index, columns=symbols)


def _feature_importance_for_model(
    model: Any,
    feature_names: tuple[str, ...],
) -> dict[str, float]:
    values = getattr(model, "feature_importances_", None)
    if values is None:
        values = getattr(model, "coef_", None)
    if values is None:
        return {}
    flattened = np.asarray(values).reshape(-1)
    if len(flattened) != len(feature_names):
        return {}
    return {
        feature: float(importance)
        for feature, importance in zip(feature_names, flattened, strict=True)
        if np.isfinite(importance)
    }


def _outcome_baseline_payload(outcome: Any) -> dict[str, float]:
    return {
        "signal_market_date_count": float(outcome.signal_market_date_count),
        "participant_count": float(outcome.participant_count),
        "mean_gross_return": float(outcome.mean_gross_return or 0.0),
        "mean_net_return": float(outcome.mean_net_return or 0.0),
    }


def _build_promoted_run_request(
    request: MethodSelectionMatrixCreateRequest,
    manifest: MethodCandidateManifest,
    specs_by_id: dict[str, list[FeatureSpec]],
) -> ResearchRunCreateRequest:
    dynamic_threshold_policy = {
        "policy_version": manifest.threshold_policy_version,
        "return_target": "open_to_open",
        "horizon_days": manifest.horizon_days,
        "lookback": manifest.volatility_lookback,
        "multiplier": manifest.multiplier,
        "estimator": "sample_standard_deviation",
        "ddof": 1,
        "complete_window_required": True,
        "continuity_policy_version": CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION,
        "horizon_scaling": "square_root",
    }
    return ResearchRunCreateRequest.model_validate(
        {
            "runtime_mode": "runtime_compatibility_mode",
            "default_bundle_version": None,
            "market": request.market,
            "symbols": request.symbols,
            "date_range": request.date_range.model_dump(mode="json"),
            "return_target": "open_to_open",
            "horizon_days": request.horizon_days,
            "features": [
                spec.model_dump(mode="json")
                for spec in specs_by_id[manifest.feature_set_id]
            ],
            "model": {
                "type": manifest.model_type,
                "params": manifest.model_params,
            },
            "strategy": {
                "type": "research_v1",
                "threshold": None,
                "top_n": manifest.top_n,
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": dynamic_threshold_policy,
                "allow_proactive_sells": True,
            },
            "execution": {
                "fees": calibration_service.CALIBRATION_FEE,
                "slippage": calibration_service.CALIBRATION_SLIPPAGE,
            },
            "validation": None,
            "baselines": [],
            "execution_route": "research_only",
        }
    )


def _promote_final_candidate(
    request: MethodSelectionMatrixCreateRequest,
    *,
    matrix_id: str,
    request_id: str,
    shortlisted_candidate_id: str,
    manifest: MethodCandidateManifest,
    artifacts: _FinalCandidateArtifacts,
    final_boundary: MethodSelectionFoldBoundary,
    final_inner_selected_candidate_id: str,
    specs_by_id: dict[str, list[FeatureSpec]],
    final_holdout_maturity_date: date | None = None,
    final_holdout_maturity_buffer_market_date_count: int = 0,
) -> str:
    """Persist one promoted run for backwards-compatible direct callers."""
    prepared = _prepare_promoted_final_candidate(
        request,
        matrix_id=matrix_id,
        request_id=request_id,
        shortlisted_candidate_id=shortlisted_candidate_id,
        manifest=manifest,
        artifacts=artifacts,
        final_boundary=final_boundary,
        final_inner_selected_candidate_id=final_inner_selected_candidate_id,
        specs_by_id=specs_by_id,
        final_holdout_maturity_date=final_holdout_maturity_date,
        final_holdout_maturity_buffer_market_date_count=(
            final_holdout_maturity_buffer_market_date_count
        ),
    )
    record_started(
        run_id=prepared.run_id,
        request_id=f"{request_id}:promoted:{prepared.run_id}",
        request=prepared.request,
    )
    record_success(
        run_id=prepared.run_id,
        request_id=f"{request_id}:promoted:{prepared.run_id}",
        request=prepared.request,
        runtime_context=prepared.runtime_context,
        response=prepared.response,
        validation_summary=None,
        warnings=prepared.response.warnings,
        request_payload_extra=prepared.registry_payload["request_payload"].get(
            "method_selection"
        ),
    )
    return prepared.run_id


def _prepare_promoted_final_candidate(
    request: MethodSelectionMatrixCreateRequest,
    *,
    matrix_id: str,
    request_id: str,
    shortlisted_candidate_id: str,
    manifest: MethodCandidateManifest,
    artifacts: _FinalCandidateArtifacts,
    final_boundary: MethodSelectionFoldBoundary,
    final_inner_selected_candidate_id: str,
    specs_by_id: dict[str, list[FeatureSpec]],
    final_holdout_maturity_date: date | None = None,
    final_holdout_maturity_buffer_market_date_count: int = 0,
) -> _PreparedPromotedRun:
    actions, scored = _final_action_rows(artifacts)
    if actions.empty:
        raise CalibrationEvaluationError(
            "Final Holdout candidate marked evaluated but produced no Action Rows."
        )
    holdout = artifacts.prepared_rows.holdout
    symbols = sorted({str(symbol) for symbol in holdout["symbol"]})
    date_index = pd.DatetimeIndex(pd.to_datetime(artifacts.fold.holdout_dates))
    weights = pd.DataFrame(0.0, index=date_index, columns=symbols)
    for signal_date, group in actions.groupby("date", sort=True):
        timestamp = pd.Timestamp(signal_date)
        weight = 1.0 / len(group)
        for symbol in group["symbol"]:
            weights.loc[timestamp, str(symbol)] = weight

    scores = _pivot_holdout_values(
        scored,
        "score",
        index=date_index,
        symbols=symbols,
    ).where(weights > 0)
    probabilities = _pivot_holdout_values(
        scored,
        "probability",
        index=date_index,
        symbols=symbols,
    ).where(weights > 0)
    prices = {
        column: _pivot_holdout_values(
            artifacts.prepared_rows.holdout,
            column,
            index=date_index,
            symbols=symbols,
        )
        for column in ("open", "high", "low", "close")
    }
    try:
        metrics, equity_curve = backtest_service.run_backtest_from_weights(
            weights=weights,
            open_df=prices["open"],
            high_df=prices["high"],
            low_df=prices["low"],
            close_df=prices["close"],
            execution=ExecutionConfig(
                fees=calibration_service.CALIBRATION_FEE,
                slippage=calibration_service.CALIBRATION_SLIPPAGE,
            ),
            market=request.market,
            return_target="open_to_open",
        )
    except Exception as exc:
        logger.exception(
            "Promoted Research Run backtest failed candidate=%s",
            manifest.candidate_id,
        )
        raise CalibrationEvaluationError(
            "Promoted Research Run artifact backtest failed."
        ) from exc
    if not metrics or not all(
        value is not None and math.isfinite(float(value))
        for value in metrics.values()
    ):
        raise CalibrationEvaluationError(
            "Promoted Research Run produced empty or non-finite metrics."
        )

    signals = backtest_service.build_signals(
        scores=scores,
        weights=weights,
        confirmation_probabilities=probabilities,
        signal_kind="holdout_evaluation",
        confirmation_threshold=calibration_service.CALIBRATION_DIRECTION_PROBABILITY_CUTOFF,
    )
    feature_names = tuple(
        feature_col_name(spec.name, spec.window, spec.source)
        for spec in specs_by_id[manifest.feature_set_id]
    )
    prediction_series = pd.Series(artifacts.scores, index=holdout.index)
    symbol_data: list[dict[str, Any]] = []
    feature_importance = _feature_importance_for_model(
        artifacts.model,
        feature_names,
    )
    for symbol, symbol_rows in holdout.groupby("symbol", sort=True):
        symbol_index = pd.to_datetime(symbol_rows["date"])
        symbol_data.append(
            {
                "symbol": str(symbol),
                "actuals": pd.Series(
                    pd.to_numeric(symbol_rows["target"], errors="coerce").to_numpy(),
                    index=symbol_index,
                ),
                "predictions": pd.Series(
                    prediction_series.loc[symbol_rows.index].to_numpy(),
                    index=symbol_index,
                ),
                "feature_importance": feature_importance,
            }
        )
    model_diagnostics = build_regression_diagnostics(symbol_data)
    run_id = f"research_run_{uuid4().hex}"
    run_request = _build_promoted_run_request(request, manifest, specs_by_id)
    version_pack = build_version_pack_payload(
        {
            "threshold_policy_version": manifest.threshold_policy_version,
            "price_basis_version": build_price_basis_version("open_to_open"),
            "benchmark_comparability_gate": False,
            "comparison_eligibility": RESEARCH_ONLY_COMPARABLE,
            "investability_screening_active": False,
            "missing_feature_policy_version": MISSING_FEATURE_POLICY_VERSION,
            "execution_cost_model_version": EXECUTION_COST_MODEL_VERSION,
            "split_policy_version": METHOD_SELECTION_FOLD_POLICY_VERSION,
            "bootstrap_policy_version": BOOTSTRAP_POLICY_VERSION,
            "ic_overlap_policy_version": IC_OVERLAP_POLICY_VERSION,
            "comparison_review_matrix_version": COMPARISON_REVIEW_MATRIX_VERSION,
            "scheduled_review_cadence": SCHEDULED_REVIEW_CADENCE,
            "model_family": calibration_service.model_service.build_model_family(
                manifest.model_type
            ),
            "training_output_contract_version": (
                calibration_service.model_service.TRAINING_OUTPUT_CONTRACT_VERSION
            ),
            "adoption_comparison_policy_version": ADOPTION_COMPARISON_POLICY_VERSION,
            "execution_route": "research_only",
        }
    )
    warnings = [
        "Final Holdout was evaluated exactly once after configuration was frozen on pre-final observations.",
        "The dynamic Direction Gate threshold is defined by the persisted threshold policy metadata; generic runtime replay is not supported for this promoted run.",
    ]
    dynamic_threshold_policy = run_request.strategy.dynamic_threshold_policy
    runtime_context = {
        "strategy": {
            "threshold": None,
            "top_n": manifest.top_n,
            "threshold_mode": "dynamic",
            "dynamic_threshold_policy": dynamic_threshold_policy.model_dump(
                mode="json"
            )
            if dynamic_threshold_policy is not None
            else None,
            "allow_proactive_sells": True,
        },
        "default_bundle_version": None,
        "config_sources": {
            "strategy": {
                "threshold": "derived_policy",
                "top_n": "request_override",
            }
        },
        "fallback_audit": {
            "strategy": {
                "threshold": {"attempted": False, "outcome": "not_needed"},
                "top_n": {"attempted": False, "outcome": "not_needed"},
            }
        },
    }
    response = ResearchRunResponse.model_validate(
        {
            "run_id": run_id,
            "feature_registry_version": FEATURE_REGISTRY_VERSION,
            "metrics": metrics,
            "equity_curve": equity_curve,
            "signals": signals,
            "validation": None,
            "model_diagnostics": model_diagnostics.model_dump(mode="json"),
            "baselines": {
                "final_candidate_outcomes": _outcome_baseline_payload(
                    artifacts.fold_result.candidate_outcomes
                ),
                "matched_baseline_outcomes": _outcome_baseline_payload(
                    artifacts.fold_result.matched_baseline_outcomes
                ),
                "eligible_date_reference_baseline_outcomes": (
                    _outcome_baseline_payload(
                        artifacts.fold_result.eligible_date_reference_baseline_outcomes
                    )
                ),
            },
            "warnings": warnings,
            "runtime_mode": run_request.runtime_mode,
            "default_bundle_version": None,
            "effective_strategy": {
                "threshold": None,
                "top_n": manifest.top_n,
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": (
                    dynamic_threshold_policy.model_dump(mode="json")
                    if dynamic_threshold_policy is not None
                    else None
                ),
            },
            "config_sources": runtime_context["config_sources"],
            "fallback_audit": runtime_context["fallback_audit"],
            "tradability_state": "research_only",
            "tradability_contract_version": ACTIVE_TRADABILITY_CONTRACT_VERSION,
            "capacity_screening_active": False,
            "missing_feature_policy_state": "complete_case_applied",
            "corporate_event_state": "clear",
            "monitor_observation_status": "skipped",
            **version_pack,
        }
    )
    response = project_live_response(response, run_request)
    request_payload_extra = {
        "matrix_id": matrix_id,
        "shortlisted_candidate_id": shortlisted_candidate_id,
        "final_candidate_id": manifest.candidate_id,
        "feature_set_id": manifest.feature_set_id,
        "final_inner_selected_candidate_id": final_inner_selected_candidate_id,
        "final_holdout_policy_version": METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
        "final_holdout_market_dates": [
            item.isoformat() for item in artifacts.fold.holdout_dates
        ],
        "final_holdout_boundary": final_boundary.model_dump(mode="json"),
        "final_holdout_maturity_policy_version": (
            METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION
        ),
        "final_holdout_maturity_date": (
            final_holdout_maturity_date.isoformat()
            if final_holdout_maturity_date is not None
            else None
        ),
        "final_holdout_maturity_buffer_market_date_count": (
            final_holdout_maturity_buffer_market_date_count
        ),
        "candidate_manifest": manifest.model_dump(mode="json"),
    }
    registry_payload = build_success_registry_payload(
        run_id=run_id,
        request_id=f"{request_id}:promoted:{run_id}",
        request=run_request,
        runtime_context=runtime_context,
        response=response,
        validation_summary=None,
        warnings=response.warnings,
        request_payload_extra=request_payload_extra,
    )
    return _PreparedPromotedRun(
        run_id=run_id,
        request=run_request,
        runtime_context=runtime_context,
        response=response,
        registry_payload=registry_payload,
    )


@dataclass(frozen=True)
class _FinalInnerSelection:
    manifests: tuple[MethodCandidateManifest, ...]
    folds: tuple[MarketDateFold, ...]
    summaries: tuple[MethodCandidateSummary, ...]
    selected_manifest: MethodCandidateManifest | None
    error: str | None = None


def _build_final_inner_selection(
    request: MethodSelectionMatrixCreateRequest,
    *,
    feature_sets: list[MethodSelectionFeatureSetManifest],
    selection_dataset: PooledModelReadyDataset,
    feature_names_by_set: dict[str, tuple[str, ...]],
    fit_counts: dict[str, int],
    model_execution: dict[str, _ModelExecutionEvidence],
    manifests: tuple[MethodCandidateManifest, ...] | None = None,
) -> _FinalInnerSelection:
    final_inner_folds = build_market_date_folds(
        tuple(sorted(set(selection_dataset.frame["date"]))),
        splits=3,
        test_size=0.2,
        purge=request.horizon_days,
    )
    manifests = manifests or tuple(
        manifest
        for feature_set in feature_sets
        for manifest in build_tuning_candidate_manifests(request, feature_set)
    )
    evaluation = _evaluate_group(
        list(manifests),
        selection_dataset.frame,
        feature_names_by_set,
        final_inner_folds,
        fit_counts,
    )
    _merge_model_execution(model_execution, evaluation.model_execution)
    summaries = tuple(
        _rank(
            [
                _summary(
                    manifest.candidate_id,
                    evaluation.candidate_folds[manifest.candidate_id],
                )
                for manifest in manifests
            ],
            outer=False,
        )
    )
    winner_id = next(
        (item.candidate_id for item in summaries if item.status == "evaluated"),
        None,
    )
    selected_manifest = next(
        (item for item in manifests if item.candidate_id == winner_id),
        None,
    )
    return _FinalInnerSelection(
        manifests=manifests,
        folds=tuple(final_inner_folds),
        summaries=summaries,
        selected_manifest=selected_manifest,
    )


def _failed_final_artifacts(
    manifest: MethodCandidateManifest,
    frame: pd.DataFrame,
    fold: MarketDateFold,
    exc: Exception,
) -> _FinalCandidateArtifacts:
    try:
        prepared_rows = calibration_service._prepare_fold_rows(fold, frame)
    except Exception:
        empty = (
            frame.iloc[0:0].copy()
            if isinstance(frame, pd.DataFrame)
            else pd.DataFrame()
        )
        prepared_rows = calibration_service._PreparedFoldRows(
            raw_train=empty,
            train=empty,
            holdout=empty,
        )
    return _FinalCandidateArtifacts(
        manifest=manifest,
        fold=fold,
        prepared_rows=prepared_rows,
        model=None,
        scores=None,
        probabilities=None,
        direction_evidence=None,
        fold_result=CalibrationCandidateFoldResult(
            fold_number=fold.number,
            status="not_evaluated",
            status_reason=(
                "Final Holdout candidate artifact evaluation failed: "
                f"{calibration_service._failure_reason(exc)}"
            ),
        ),
    )


def _final_configuration_group_id(manifest: MethodCandidateManifest) -> str:
    payload = manifest.model_dump(mode="json")
    payload.pop("candidate_id", None)
    payload.pop("phase", None)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return f"final_configuration_{digest}"


def _build_final_holdout_result(
    request: MethodSelectionMatrixCreateRequest,
    *,
    matrix_id: str,
    request_id: str,
    shortlist_summary: MethodCandidateSummary,
    feature_sets: list[MethodSelectionFeatureSetManifest],
    specs_by_id: dict[str, list[FeatureSpec]],
    feature_names_by_set: dict[str, tuple[str, ...]],
    selection_dataset: PooledModelReadyDataset,
    full_dataset: PooledModelReadyDataset,
    selection_dates: tuple[date, ...],
    final_holdout_dates: tuple[date, ...],
    fit_counts: dict[str, int],
    phase_b_by_id: dict[str, MethodCandidateManifest],
    model_execution: dict[str, _ModelExecutionEvidence],
    final_inner_selection: _FinalInnerSelection | None = None,
    final_holdout_artifacts_cache: dict[str, _FinalCandidateArtifacts] | None = None,
    prepared_runs: list[_PreparedPromotedRun] | None = None,
    final_inner_selection_reuse_mode: str = "computed",
    final_holdout_maturity_date: date | None = None,
    final_holdout_maturity_buffer_market_date_count: int = 0,
) -> MethodSelectionFinalHoldoutResult:
    del phase_b_by_id
    try:
        final_fold = _final_holdout_fold(
            selection_dates,
            final_holdout_dates,
            request.horizon_days,
        )
    except Exception as exc:
        return MethodSelectionFinalHoldoutResult(
            shortlisted_candidate_id=shortlist_summary.candidate_id,
            final_holdout_policy_version=METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
            final_holdout_market_dates=list(final_holdout_dates),
            final_holdout_boundary=MethodSelectionFoldBoundary(
                number=6,
                train_market_date_count=0,
                purge_market_date_count=0,
                holdout_market_date_count=len(final_holdout_dates),
                holdout_date_start=final_holdout_dates[0]
                if final_holdout_dates
                else None,
                holdout_date_end=final_holdout_dates[-1]
                if final_holdout_dates
                else None,
            ),
            final_holdout_maturity_date=final_holdout_maturity_date,
            final_holdout_maturity_buffer_market_date_count=(
                final_holdout_maturity_buffer_market_date_count
            ),
            status="not_evaluated",
            status_reason=calibration_service._failure_reason(exc),
        )

    final_boundary = _boundary(final_fold, full_dataset.frame)
    if final_inner_selection is None:
        try:
            final_inner_selection = _build_final_inner_selection(
                request,
                feature_sets=feature_sets,
                selection_dataset=selection_dataset,
                feature_names_by_set=feature_names_by_set,
                fit_counts=fit_counts,
                model_execution=model_execution,
            )
        except Exception as exc:
            return MethodSelectionFinalHoldoutResult(
                shortlisted_candidate_id=shortlist_summary.candidate_id,
                final_holdout_policy_version=METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
                final_holdout_market_dates=list(final_holdout_dates),
                final_holdout_boundary=final_boundary,
                final_holdout_maturity_date=final_holdout_maturity_date,
                final_holdout_maturity_buffer_market_date_count=(
                    final_holdout_maturity_buffer_market_date_count
                ),
                status="not_evaluated",
                status_reason=(
                    "Final inner selection could not be formed: "
                    f"{calibration_service._failure_reason(exc)}"
                ),
            )

    if final_inner_selection.error is not None:
        return MethodSelectionFinalHoldoutResult(
            shortlisted_candidate_id=shortlist_summary.candidate_id,
            final_holdout_policy_version=METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
            final_holdout_market_dates=list(final_holdout_dates),
            final_holdout_boundary=final_boundary,
            final_holdout_maturity_date=final_holdout_maturity_date,
            final_holdout_maturity_buffer_market_date_count=(
                final_holdout_maturity_buffer_market_date_count
            ),
            final_inner_selection_reuse_mode=final_inner_selection_reuse_mode,
            status="not_evaluated",
            status_reason=final_inner_selection.error,
        )

    final_inner_winner = final_inner_selection.selected_manifest
    base_result = {
        "shortlisted_candidate_id": shortlist_summary.candidate_id,
        "final_holdout_policy_version": METHOD_SELECTION_FINAL_HOLDOUT_POLICY_VERSION,
        "final_holdout_market_dates": list(final_holdout_dates),
        "final_holdout_boundary": final_boundary,
        "final_holdout_maturity_date": final_holdout_maturity_date,
        "final_holdout_maturity_buffer_market_date_count": (
            final_holdout_maturity_buffer_market_date_count
        ),
        "final_inner_folds": [
            _boundary(inner_fold, selection_dataset.frame)
            for inner_fold in final_inner_selection.folds
        ],
        "final_inner_summaries": list(final_inner_selection.summaries),
        "final_inner_selection_reuse_mode": final_inner_selection_reuse_mode,
        "final_holdout_evaluation_reuse_mode": "computed",
        "final_inner_selected_candidate_id": (
            final_inner_winner.candidate_id if final_inner_winner else None
        ),
    }
    if final_inner_winner is None:
        status = (
            "no_opinion"
            if any(
                item.status == "no_opinion"
                for item in final_inner_selection.summaries
            )
            else "not_evaluated"
        )
        reason = next(
            (
                item.status_reason
                for item in final_inner_selection.summaries
                if item.status_reason
            ),
            "No final inner candidate produced complete evidence.",
        )
        return MethodSelectionFinalHoldoutResult(
            **base_result,
            status=status,
            status_reason=reason,
        )

    final_manifest = final_inner_winner
    cache = final_holdout_artifacts_cache if final_holdout_artifacts_cache is not None else {}
    final_artifacts = cache.get(final_manifest.candidate_id)
    if final_artifacts is None:
        fit_counts["final_holdout_execution"] += 1
        try:
            final_artifacts = _evaluate_final_candidate(
                final_manifest,
                full_dataset.frame,
                feature_names_by_set,
                final_fold,
                fit_counts,
            )
        except Exception as exc:
            logger.exception(
                "Final Holdout candidate artifact preparation failed candidate=%s",
                final_manifest.candidate_id,
            )
            final_artifacts = _failed_final_artifacts(
                final_manifest,
                full_dataset.frame,
                final_fold,
                exc,
            )
        cache[final_manifest.candidate_id] = final_artifacts
        execution = model_execution.setdefault(
            final_manifest.model_type, _ModelExecutionEvidence()
        )
        if final_artifacts.model is not None:
            execution.evaluated_group_fold_count += 1
        elif final_artifacts.fold_result.status_reason:
            execution.unavailable_reasons.append(
                final_artifacts.fold_result.status_reason
            )
    else:
        fit_counts["final_holdout_reuse"] += 1
        base_result["final_holdout_evaluation_reuse_mode"] = "deterministic_reused"

    if final_artifacts.fold_result.status != "evaluated":
        return MethodSelectionFinalHoldoutResult(
            **base_result,
            final_candidate_id=final_manifest.candidate_id,
            final_candidate_manifest=final_manifest,
            final_holdout_evaluation=final_artifacts.fold_result,
            status=final_artifacts.fold_result.status,
            status_reason=final_artifacts.fold_result.status_reason,
        )

    try:
        if prepared_runs is None:
            promoted_run_id = _promote_final_candidate(
                request,
                matrix_id=matrix_id,
                request_id=request_id,
                shortlisted_candidate_id=shortlist_summary.candidate_id,
                manifest=final_manifest,
                artifacts=final_artifacts,
                final_boundary=final_boundary,
                final_inner_selected_candidate_id=final_inner_winner.candidate_id,
                specs_by_id=specs_by_id,
                final_holdout_maturity_date=final_holdout_maturity_date,
                final_holdout_maturity_buffer_market_date_count=(
                    final_holdout_maturity_buffer_market_date_count
                ),
            )
        else:
            prepared = _prepare_promoted_final_candidate(
                request,
                matrix_id=matrix_id,
                request_id=request_id,
                shortlisted_candidate_id=shortlist_summary.candidate_id,
                manifest=final_manifest,
                artifacts=final_artifacts,
                final_boundary=final_boundary,
                final_inner_selected_candidate_id=final_inner_winner.candidate_id,
                specs_by_id=specs_by_id,
                final_holdout_maturity_date=final_holdout_maturity_date,
                final_holdout_maturity_buffer_market_date_count=(
                    final_holdout_maturity_buffer_market_date_count
                ),
            )
            prepared_runs.append(prepared)
            promoted_run_id = prepared.run_id
    except Exception as exc:
        logger.exception(
            "Final Holdout candidate promotion preparation failed candidate=%s",
            final_manifest.candidate_id,
        )
        return MethodSelectionFinalHoldoutResult(
            **base_result,
            final_candidate_id=final_manifest.candidate_id,
            final_candidate_manifest=final_manifest,
            final_holdout_evaluation=final_artifacts.fold_result,
            status="not_evaluated",
            status_reason=(
                "Promoted Research Run preparation failed: "
                f"{calibration_service._failure_reason(exc)}"
            ),
        )

    return MethodSelectionFinalHoldoutResult(
        **base_result,
        final_candidate_id=final_manifest.candidate_id,
        final_candidate_manifest=final_manifest,
        final_holdout_evaluation=final_artifacts.fold_result,
        status="promoted",
        promoted_research_run_id=promoted_run_id,
    )


def _maximum_fit_counts(
    request: MethodSelectionMatrixCreateRequest,
    *,
    phase_a_count: int,
    outer_fold_count: int,
    feature_set_count: int = 18,
    shortlist_count: int = 3,
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
    final_parameter_groups = feature_set_count * parameter_groups
    maximum_regression += (
        final_parameter_groups * inner_fold_count + shortlist_count
    )
    maximum_gates += (
        final_parameter_groups * 9 * inner_fold_count + shortlist_count
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
    datasets = _load_method_selection_datasets(
        request,
        _default_specs(),
        feature_names_by_set,
    )
    dataset = datasets.selection
    full_dataset = datasets.full
    selection_dates = datasets.selection_dates
    final_holdout_dates = datasets.final_holdout_dates
    final_holdout_maturity_date = datasets.final_holdout_maturity_date
    final_holdout_maturity_buffer_market_date_count = (
        datasets.final_holdout_maturity_buffer_market_date_count
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

    ranked_outer_summaries = _rank(outer_summaries, outer=True)
    shortlist = [
        summary
        for summary in ranked_outer_summaries
        if summary.status == "evaluated"
    ][:3]
    if shortlist:
        final_inner_candidate_manifests = tuple(
            manifest
            for feature_set in feature_sets
            for manifest in build_tuning_candidate_manifests(request, feature_set)
        )
        try:
            final_inner_selection = _build_final_inner_selection(
                request,
                feature_sets=feature_sets,
                selection_dataset=dataset,
                feature_names_by_set=feature_names_by_set,
                fit_counts=fit_counts,
                model_execution=model_execution,
                manifests=final_inner_candidate_manifests,
            )
        except Exception as exc:
            logger.exception("Final inner catalog evaluation failed")
            final_inner_selection = _FinalInnerSelection(
                manifests=final_inner_candidate_manifests,
                folds=(),
                summaries=(),
                selected_manifest=None,
                error=(
                    "Final inner selection failed: "
                    f"{calibration_service._failure_reason(exc)}"
                ),
            )
    else:
        final_inner_candidate_manifests = ()
        final_inner_selection = _FinalInnerSelection(
            manifests=(),
            folds=(),
            summaries=(),
            selected_manifest=None,
        )
    final_holdout_results: list[MethodSelectionFinalHoldoutResult] = []
    prepared_runs: list[_PreparedPromotedRun] = []
    final_holdout_artifacts_cache: dict[str, _FinalCandidateArtifacts] = {}
    resolved_matrix_id = matrix_id or f"method_selection_{uuid4().hex}"
    for shortlist_index, shortlist_summary in enumerate(shortlist):
        final_holdout_results.append(
            _build_final_holdout_result(
                request,
                matrix_id=resolved_matrix_id,
                request_id=request_id,
                shortlist_summary=shortlist_summary,
                feature_sets=feature_sets,
                specs_by_id=specs_by_id,
                feature_names_by_set=feature_names_by_set,
                selection_dataset=dataset,
                full_dataset=full_dataset,
                selection_dates=selection_dates,
                final_holdout_dates=final_holdout_dates,
                fit_counts=fit_counts,
                phase_b_by_id=phase_b_by_id,
                model_execution=model_execution,
                final_inner_selection=final_inner_selection,
                final_holdout_artifacts_cache=final_holdout_artifacts_cache,
                prepared_runs=prepared_runs,
                final_inner_selection_reuse_mode=(
                    "computed" if shortlist_index == 0 else "deterministic_reused"
                ),
                final_holdout_maturity_date=final_holdout_maturity_date,
                final_holdout_maturity_buffer_market_date_count=(
                    final_holdout_maturity_buffer_market_date_count
                ),
            )
        )

    configuration_groups: dict[str, list[int]] = defaultdict(list)
    for index, result in enumerate(final_holdout_results):
        if result.final_candidate_manifest is not None:
            configuration_groups[
                _final_configuration_group_id(result.final_candidate_manifest)
            ].append(index)
    prepared_by_run_id = {item.run_id: item for item in prepared_runs}
    for group_id, indexes in configuration_groups.items():
        if len(indexes) < 2:
            continue
        group_run_ids = [
            final_holdout_results[index].promoted_research_run_id
            for index in indexes
            if final_holdout_results[index].promoted_research_run_id is not None
        ]
        for index in indexes:
            result = final_holdout_results[index]
            own_run_id = result.promoted_research_run_id
            duplicate_run_ids = [
                run_id for run_id in group_run_ids if run_id != own_run_id
            ]
            final_holdout_results[index] = result.model_copy(
                update={
                    "same_final_configuration": True,
                    "final_configuration_group_id": group_id,
                    "duplicate_configuration_run_ids": duplicate_run_ids,
                }
            )
            if own_run_id is not None and own_run_id in prepared_by_run_id:
                method_selection_payload = prepared_by_run_id[own_run_id].registry_payload[
                    "request_payload"
                ]["method_selection"]
                method_selection_payload.update(
                    {
                        "same_final_configuration": True,
                        "final_configuration_group_id": group_id,
                        "duplicate_configuration_run_ids": duplicate_run_ids,
                    }
                )
    promoted_research_run_ids = [
        item.promoted_research_run_id
        for item in final_holdout_results
        if item.promoted_research_run_id is not None
    ]
    maximum_regression, maximum_gates = _maximum_fit_counts(
        request,
        phase_a_count=len(phase_a_manifests),
        outer_fold_count=len(outer_folds),
        feature_set_count=len(feature_sets),
        shortlist_count=len(final_holdout_results),
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
        final_inner_candidate_count=len(final_inner_candidate_manifests),
        final_inner_execution_count=(
            0 if final_inner_selection.error is not None else 1
        ),
        final_inner_reuse_count=(
            max(len(shortlist) - 1, 0)
            if final_inner_selection.error is None
            else 0
        ),
        final_holdout_execution_count=fit_counts["final_holdout_execution"],
        final_holdout_reuse_count=fit_counts["final_holdout_reuse"],
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
        matrix_id=resolved_matrix_id,
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
        final_inner_candidate_manifests=list(final_inner_candidate_manifests),
        final_holdout_maturity_policy_version=(
            METHOD_SELECTION_FINAL_HOLDOUT_MATURITY_POLICY_VERSION
        ),
        final_holdout_maturity_date=final_holdout_maturity_date,
        final_holdout_maturity_buffer_market_date_count=(
            final_holdout_maturity_buffer_market_date_count
        ),
        outer_folds=records,
        outer_candidate_summaries=ranked_outer_summaries,
        shortlist=shortlist,
        final_holdout_results=final_holdout_results,
        promoted_research_run_ids=promoted_research_run_ids,
        comparison_caveats=[caveat_payload] if caveat_payload else [],
        resource_evidence=resource_evidence,
        model_availability=_availability(
            phase_a_manifests
            + list(phase_b_by_id.values())
            + list(final_inner_candidate_manifests),
            model_execution,
        ),
        comparability_evidence=comparability_evidence,
        created_at=utc_now(),
    )
    persist_method_selection_batch(
        response.model_dump(mode="json"),
        [item.registry_payload for item in prepared_runs],
    )
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
