from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)

from backend.platform.errors import (
    DataNotFoundError,
    InsufficientDataError,
    UnsupportedConfigurationError,
)
from backend.research.contracts.runs import (
    DirectionClassificationDiagnostics,
    Metrics,
    RegressionDiagnostics,
    ResearchRunCreateRequest,
    ResearchRunResponse,
    ValidationSummary,
)
from backend.research.contracts.runtime_metadata import (
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
)
from backend.research.domain.version_pack import build_version_pack_payload
from backend.research.services.adaptive import record_run_adaptive_exclusion
from backend.research.services.eligibility import (
    exclude_non_official_rows_on_official_no_data,
    load_official_no_data_dates,
)
from backend.research.services.run_foundations import (
    build_run_foundation_context,
    build_run_peer_feature_map,
    dispatch_run_execution_route,
    materialize_run_factors,
    persist_run_factor_observations,
    persist_run_peer_outputs,
)
from backend.research.services.tradability import build_p3_summary
from backend.shared.analytics import backtest as backtest_service
from backend.shared.analytics import baselines as baseline_service
from backend.shared.analytics import features as feature_engine
from backend.shared.analytics import market_data as data_service
from backend.shared.analytics import models as model_service
from backend.shared.analytics import validation as validation_service
from backend.shared.analytics.strategy import (
    ADOPTION_COMPARISON_POLICY_VERSION,
    BOOTSTRAP_POLICY_VERSION,
    COMPARISON_REVIEW_MATRIX_VERSION,
    IC_OVERLAP_POLICY_VERSION,
    SCHEDULED_REVIEW_CADENCE,
    ResearchStrategyConfig,
    build_comparison_eligibility,
    build_price_basis_version,
    build_split_policy_version,
    build_threshold_policy_version,
    resolve_runtime_strategy,
)

logger = logging.getLogger(__name__)


@dataclass
class ResearchRunExecutionArtifacts:
    response: ResearchRunResponse
    runtime_context: dict
    validation_summary: ValidationSummary | None
    warnings: list[str]


def _metrics_are_finite(metrics: dict) -> bool:
    if not metrics:
        return False
    try:
        return all(math.isfinite(float(value)) for value in metrics.values())
    except (TypeError, ValueError, OverflowError):
        return False


def build_feature_config(request: ResearchRunCreateRequest) -> tuple[dict, dict]:
    config: dict = {}
    shift_map: dict = {}

    if not request.features:
        raise UnsupportedConfigurationError(
            "features must include at least one feature spec."
        )

    for spec in request.features:
        config.setdefault(spec.name, []).append(
            {"window": spec.window, "source": spec.source}
        )
        col_name = feature_engine.feature_col_name(spec.name, spec.window, spec.source)
        shift_map[col_name] = spec.shift

    for key in feature_engine.FEATURE_DEFINITION_BY_NAME:
        items = config.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            raise UnsupportedConfigurationError(
                f"Feature config for '{key}' must be a list of window/source entries."
            )

        try:
            unique = {(item["window"], item["source"]) for item in items}
        except (KeyError, TypeError) as exc:
            raise UnsupportedConfigurationError(
                f"Feature config for '{key}' must contain window/source pairs."
            ) from exc

        config[key] = [{"window": w, "source": s} for w, s in sorted(unique)]

    return config, shift_map


def apply_feature_shifts(df: pd.DataFrame, shift_map: dict, symbol: str) -> None:
    for column, shift in shift_map.items():
        if column not in df.columns:
            raise UnsupportedConfigurationError(
                f"[{symbol}] Expected feature column '{column}' not found after feature generation."
            )
        if shift < 1:
            raise UnsupportedConfigurationError(
                f"[{symbol}] Feature shift for '{column}' must be >= 1."
            )
        df[column] = df[column].shift(shift)


def load_symbol_data(
    run_id: str,
    request: ResearchRunCreateRequest,
    symbol: str,
    feature_config: dict,
    shift_map: dict,
    test_size: float,
    peer_feature_map: dict[str, dict[pd.Timestamp, dict[str, float]]] | None = None,
    official_no_data_dates: set[date] | None = None,
) -> dict:
    logger.info("Loading symbol=%s market=%s", symbol, request.market)
    df = data_service.get_data(
        symbols=symbol,
        start_date=request.date_range.start,
        end_date=request.date_range.end,
        market=request.market,
    )
    if df.empty:
        raise DataNotFoundError(
            f"No data found for symbol '{symbol}' in the specified date range."
        )
    if request.market == "TW" and "source" in df.columns:
        df = exclude_non_official_rows_on_official_no_data(
            df,
            official_no_data_dates
            if official_no_data_dates is not None
            else load_official_no_data_dates(
                start_date=request.date_range.start,
                end_date=request.date_range.end,
            ),
        )

    unshifted_features = feature_engine.add_features(df.copy(), feature_config)
    df_features = unshifted_features.copy()
    apply_feature_shifts(df_features, shift_map, symbol)
    df_features, factor_materializations = materialize_run_factors(
        request,
        run_id=run_id,
        symbol=symbol,
        df_features=df_features,
    )
    df_features = attach_peer_features_to_frame(
        df_features,
        symbol=symbol,
        peer_feature_map=peer_feature_map or {},
    )

    df_model, X, y = model_service.prepare_training_data(
        df_features,
        return_target=request.return_target,
        horizon_days=request.horizon_days,
    )
    if X.empty or y.empty:
        raise InsufficientDataError(
            f"[{symbol}] No training rows remain after feature generation and target alignment."
        )

    try:
        purge = model_service.target_lookahead(
            request.return_target, request.horizon_days
        )
        X_train, X_test, y_train, y_test = model_service.time_series_split(
            X, y, test_size=test_size, purge=purge
        )
    except ValueError as exc:
        raise InsufficientDataError(f"[{symbol}] {exc}") from exc

    model = model_service.fit_regressor(
        model_type=request.model.type,
        X_train=X_train,
        y_train=y_train,
        model_params=request.model.params,
    )
    preds = model.predict(X_test)
    predictions = pd.Series(preds, index=X_test.index, name=symbol)

    result = {
        "symbol": symbol,
        "df_model": df_model,
        "X": X,
        "y": y,
        "scores": predictions,
        "actuals": y_test.rename(symbol),
        "predictions": predictions,
        "feature_names": list(X_train.columns),
        "prediction_features": df_features.reindex(columns=X.columns).dropna(),
        "prospective_prediction_features": unshifted_features.reindex(
            columns=X.columns
        ).dropna(),
        "feature_importance": _extract_feature_importance(model, list(X_train.columns)),
        "open": df_model.loc[X_test.index, "open"].rename(symbol),
        "high": df_model.loc[X_test.index, "high"].rename(symbol),
        "low": df_model.loc[X_test.index, "low"].rename(symbol),
        "close": df_model.loc[X_test.index, "close"].rename(symbol),
        "volume": df_model.loc[X_test.index, "volume"].rename(symbol),
        "factor_materializations": factor_materializations,
    }
    direction_config = request.direction_model
    if direction_config is not None:
        direction_train = (
            y_train > direction_config.positive_return_threshold
        ).astype(int)
        classifier, unavailable_reason, calibration_size = (
            model_service.fit_calibrated_direction_classifier(
                model_type=direction_config.type,
                X_train=X_train,
                y_train=direction_train,
                model_params=direction_config.params,
                purge=purge,
            )
        )
        result.update(
            {
                "direction_config": direction_config,
                "direction_unavailable_reason": unavailable_reason,
                "direction_calibration_sample_count": calibration_size,
            }
        )
        if classifier is not None:
            positive_class_index = list(classifier.classes_).index(1)
            result["direction_actuals"] = (
                y_test > direction_config.positive_return_threshold
            ).astype(int)
            result["up_probabilities"] = pd.Series(
                classifier.predict_proba(X_test)[:, positive_class_index],
                index=X_test.index,
                name=symbol,
            )
    return result


def build_forward_opinion_signals(
    symbol_data: list[dict],
    request: ResearchRunCreateRequest,
    strategy: ResearchStrategyConfig,
) -> tuple[list[dict], str | None]:
    direction_config = request.direction_model
    if direction_config is None:
        return [], None
    if not symbol_data:
        return [], "Prospective opinion unavailable: no symbol data was loaded."
    purge = model_service.target_lookahead(
        request.return_target, request.horizon_days
    )
    if purge == 0:
        return (
            [],
            "Prospective opinion unavailable: the configured target has no "
            "unlabeled forward feature row.",
        )
    loaded_symbols = {item.get("symbol") for item in symbol_data}
    if loaded_symbols != set(request.symbols) or len(symbol_data) != len(
        request.symbols
    ):
        return (
            [],
            "Prospective opinion unavailable: loaded symbols do not match the "
            "requested universe.",
        )

    feature_key = (
        "prospective_prediction_features"
        if request.prospective_evidence is not None
        else "prediction_features"
    )
    latest_dates = [item[feature_key].index.max() for item in symbol_data]
    if any(pd.isna(value) for value in latest_dates) or len(set(latest_dates)) != 1:
        return (
            [],
            "Prospective opinion unavailable: requested symbols do not share one "
            "latest feature date.",
        )
    as_of = latest_dates[0]
    if (
        request.prospective_evidence is not None
        and as_of.date() != request.prospective_evidence.basis_date
    ):
        return (
            [],
            "Prospective opinion unavailable: strict evidence basis_date does not "
            "match the latest unshifted feature date.",
        )

    scores: dict[str, float] = {}
    probabilities: dict[str, float] = {}
    for item in symbol_data:
        X = item["X"]
        y = item["y"]
        forward_features = item[feature_key].loc[[as_of]]
        regressor = model_service.fit_regressor(
            model_type=request.model.type,
            X_train=X,
            y_train=y,
            model_params=request.model.params,
        )
        classifier, unavailable_reason, _ = (
            model_service.fit_calibrated_direction_classifier(
                model_type=direction_config.type,
                X_train=X,
                y_train=(y > direction_config.positive_return_threshold).astype(int),
                model_params=direction_config.params,
                purge=purge,
            )
        )
        if classifier is None:
            return (
                [],
                f"[{item['symbol']}] Prospective direction calibration unavailable: "
                f"{unavailable_reason or 'classifier was not produced.'}",
            )
        positive_class_index = list(classifier.classes_).index(1)
        score = float(regressor.predict(forward_features)[0])
        probability = float(
            classifier.predict_proba(forward_features)[0][positive_class_index]
        )
        if (
            not math.isfinite(score)
            or not math.isfinite(probability)
            or not 0.0 <= probability <= 1.0
        ):
            return (
                [],
                f"[{item['symbol']}] Prospective opinion unavailable: model output "
                "was non-finite or outside the probability range.",
            )
        scores[item["symbol"]] = score
        probabilities[item["symbol"]] = probability

    scores_df = pd.DataFrame(scores, index=[as_of])
    probabilities_df = pd.DataFrame(probabilities, index=[as_of])
    weights = backtest_service.build_target_weights(
        scores=scores_df,
        strategy=strategy,
        confirmation_probabilities=probabilities_df,
        confirmation_threshold=direction_config.confirmation_probability_threshold,
    )
    signals = backtest_service.build_signals(
        scores_df,
        weights,
        probabilities_df,
        signal_kind="forward_opinion",
        confirmation_threshold=direction_config.confirmation_probability_threshold,
    )
    return signals, None


def build_holdout_confirmation_probabilities(
    symbol_data: list[dict],
    scores: pd.DataFrame,
    request: ResearchRunCreateRequest,
) -> tuple[pd.DataFrame | None, str | None]:
    if request.direction_model is None:
        return None, None

    unavailable = [
        item["symbol"]
        for item in symbol_data
        if item.get("up_probabilities") is None
    ]
    if unavailable:
        return (
            pd.DataFrame(float("nan"), index=scores.index, columns=scores.columns),
            "Direction confirmation unavailable for "
            f"{', '.join(unavailable)}; hybrid backtest positions were held at zero.",
        )

    probabilities = pd.concat(
        [item["up_probabilities"] for item in symbol_data], axis=1
    )
    return probabilities.reindex(index=scores.index, columns=scores.columns), None


def _extract_feature_importance(model: object, feature_names: list[str]) -> dict[str, float]:
    raw_importance = getattr(model, "feature_importances_", None)
    if raw_importance is None:
        return {}

    values = list(raw_importance)
    if len(values) != len(feature_names):
        return {}

    return {
        feature: float(importance)
        for feature, importance in zip(feature_names, values)
        if pd.notna(importance)
    }


def _clean_metric(value: float) -> float | None:
    return float(value) if pd.notna(value) else None


def build_direction_classification_diagnostics(
    symbol_data: list[dict],
) -> DirectionClassificationDiagnostics | None:
    configured = [item for item in symbol_data if item.get("direction_config")]
    if not configured:
        return None

    config = configured[0]["direction_config"]
    unavailable = [
        f"{item['symbol']}: {item['direction_unavailable_reason']}"
        for item in configured
        if item.get("direction_unavailable_reason")
    ]
    if unavailable or len(configured) != len(symbol_data):
        return DirectionClassificationDiagnostics(
            evaluation_status="not_evaluated",
            status_reason="; ".join(unavailable)
            or "Direction model was not evaluated for the complete symbol universe.",
            positive_return_threshold=config.positive_return_threshold,
            confirmation_probability_threshold=(
                config.confirmation_probability_threshold
            ),
            calibration_policy_version=config.calibration_policy_version,
            confirmation_policy_version=config.confirmation_policy_version,
        )

    frames = []
    for item in configured:
        actuals = item.get("direction_actuals")
        probabilities = item.get("up_probabilities")
        if actuals is None or probabilities is None:
            return DirectionClassificationDiagnostics(
                evaluation_status="not_evaluated",
                status_reason=(
                    "Direction model outputs are incomplete for the symbol universe."
                ),
                positive_return_threshold=config.positive_return_threshold,
                confirmation_probability_threshold=(
                    config.confirmation_probability_threshold
                ),
                calibration_policy_version=config.calibration_policy_version,
                confirmation_policy_version=config.confirmation_policy_version,
            )
        frame = pd.DataFrame(
            {"actual": actuals, "probability": probabilities.reindex(actuals.index)}
        ).dropna()
        if frame.empty:
            return DirectionClassificationDiagnostics(
                evaluation_status="not_evaluated",
                status_reason="Direction model produced no evaluable holdout rows.",
                positive_return_threshold=config.positive_return_threshold,
                confirmation_probability_threshold=(
                    config.confirmation_probability_threshold
                ),
                calibration_policy_version=config.calibration_policy_version,
                confirmation_policy_version=config.confirmation_policy_version,
            )
        frames.append(frame)

    diagnostics_frame = pd.concat(frames)
    actual = diagnostics_frame["actual"].astype(int)
    probability = diagnostics_frame["probability"].astype(float)
    predicted = (probability >= config.confirmation_probability_threshold).astype(int)
    has_both_classes = actual.nunique() == 2
    return DirectionClassificationDiagnostics(
        evaluation_status="evaluated",
        sample_count=len(diagnostics_frame),
        positive_return_threshold=config.positive_return_threshold,
        confirmation_probability_threshold=config.confirmation_probability_threshold,
        calibration_policy_version=config.calibration_policy_version,
        confirmation_policy_version=config.confirmation_policy_version,
        calibration_sample_count=sum(
            item["direction_calibration_sample_count"] for item in configured
        ),
        positive_prevalence=float(actual.mean()),
        confusion_matrix=confusion_matrix(actual, predicted, labels=[0, 1]).tolist(),
        precision=float(precision_score(actual, predicted, zero_division=0)),
        recall=float(recall_score(actual, predicted, zero_division=0)),
        roc_auc=float(roc_auc_score(actual, probability))
        if has_both_classes
        else None,
        pr_auc=float(average_precision_score(actual, probability))
        if has_both_classes
        else None,
        brier=float(brier_score_loss(actual, probability)),
    )


def build_regression_diagnostics(symbol_data: list[dict]) -> RegressionDiagnostics:
    direction_diagnostics = build_direction_classification_diagnostics(symbol_data)
    frames: list[pd.DataFrame] = []
    feature_importance: dict[str, list[float]] = {}

    for item in symbol_data:
        actuals = item.get("actuals", item.get("y"))
        predictions = item.get("predictions", item.get("scores"))
        if actuals is None or predictions is None:
            continue
        predictions = predictions.reindex(actuals.index)
        frame = pd.DataFrame(
            {
                "actual": actuals,
                "predicted": predictions,
            }
        ).dropna()
        if frame.empty:
            continue

        frame["symbol"] = item["symbol"]
        frame["residual"] = frame["actual"] - frame["predicted"]
        frames.append(frame)

        for feature, importance in item.get("feature_importance", {}).items():
            feature_importance.setdefault(feature, []).append(float(importance))

    if not frames:
        return RegressionDiagnostics(direction_classification=direction_diagnostics)

    diagnostics_frame = pd.concat(frames).sort_index()
    residuals = diagnostics_frame["residual"]
    rmse = float((residuals.pow(2).mean()) ** 0.5)
    mae = float(residuals.abs().mean())
    rank_ic = None
    linear_ic = None
    if len(diagnostics_frame) > 1:
        rank_ic = _clean_metric(
            diagnostics_frame["actual"].corr(
                diagnostics_frame["predicted"], method="spearman"
            )
        )
        linear_ic = _clean_metric(
            diagnostics_frame["actual"].corr(
                diagnostics_frame["predicted"], method="pearson"
            )
        )

    sample = diagnostics_frame.tail(200)
    diagnostic_points = [
        {
            "date": dt.date() if hasattr(dt, "date") else dt,
            "symbol": str(row["symbol"]),
            "actual": float(row["actual"]),
            "predicted": float(row["predicted"]),
            "residual": float(row["residual"]),
        }
        for dt, row in sample.iterrows()
    ]
    importance_points = [
        {
            "feature": feature,
            "importance": float(sum(values) / len(values)),
        }
        for feature, values in feature_importance.items()
        if values
    ]
    importance_points.sort(key=lambda item: item["importance"], reverse=True)

    return RegressionDiagnostics(
        sample_count=int(len(diagnostics_frame)),
        rmse=rmse,
        mae=mae,
        rank_ic=rank_ic,
        linear_ic=linear_ic,
        actual_vs_predicted=diagnostic_points,
        residuals=diagnostic_points,
        feature_importance=importance_points,
        direction_classification=direction_diagnostics,
    )


def attach_peer_features_to_frame(
    df_features: pd.DataFrame,
    *,
    symbol: str,
    peer_feature_map: dict[str, dict[pd.Timestamp, dict[str, float]]],
) -> pd.DataFrame:
    timeline = peer_feature_map.get(symbol)
    if not timeline:
        return df_features
    peer_frame = (
        pd.DataFrame.from_dict(timeline, orient="index")
        .sort_index()
        .reindex(pd.to_datetime(df_features.index))
        .ffill()
        .fillna(0.0)
    )
    augmented = df_features.copy()
    for column in peer_frame.columns:
        augmented[column] = peer_frame[column].to_numpy()
    return augmented


def compute_validation_summary(
    symbol_data: list[dict],
    request: ResearchRunCreateRequest,
    strategy: ResearchStrategyConfig,
) -> ValidationSummary | None:
    if request.validation is None:
        return None

    def not_evaluated(reason: str) -> ValidationSummary:
        return ValidationSummary(
            method=request.validation.method,
            evaluation_status="not_evaluated",
            status_reason=reason,
            metrics={},
        )

    purge = model_service.target_lookahead(
        request.return_target, request.horizon_days
    )
    loaded_symbols = [data.get("symbol") for data in symbol_data]
    if (
        len(symbol_data) != len(request.symbols)
        or len(loaded_symbols) != len(set(loaded_symbols))
        or set(loaded_symbols) != set(request.symbols)
    ):
        return not_evaluated(
            "Validation symbol data does not match the requested universe."
        )

    common_index = symbol_data[0]["X"].index
    for data in symbol_data:
        if data["X"].index.has_duplicates:
            return not_evaluated(
                f"[{data['symbol']}] Validation feature dates contain duplicates."
            )
        common_index = common_index.intersection(data["X"].index, sort=False)
    common_index = common_index.sort_values()
    if common_index.empty:
        return not_evaluated(
            "Validation symbols have no common model-ready dates."
        )
    try:
        folds = validation_service.generate_splits(
            length=len(common_index),
            method=request.validation.method,
            splits=request.validation.splits,
            test_size=request.validation.test_size,
            purge=purge,
        )
    except ValueError as exc:
        return not_evaluated(
            f"Validation cannot run on the common-date sample: {exc}"
        )
    if not folds:
        return not_evaluated("Validation produced no common-date folds.")

    metrics_list: list[dict] = []
    for train_range, test_range in folds:
        train_index = common_index[list(train_range)]
        test_index = common_index[list(test_range)]
        fold_scores: list[pd.Series] = []
        fold_probabilities: list[pd.Series] = []
        fold_prices: dict[str, list[pd.Series]] = {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
        }
        for data in symbol_data:
            symbol = data["symbol"]
            X = data["X"]
            y = data["y"]
            X_train = X.reindex(train_index)
            y_train = y.reindex(train_index)
            X_test = X.reindex(test_index)

            if (
                X_train.empty
                or X_test.empty
                or X_train.isna().any().any()
                or X_test.isna().any().any()
                or y_train.isna().any()
            ):
                return not_evaluated(
                    f"[{symbol}] Validation split is incomplete on common dates."
                )

            model = model_service.fit_regressor(
                model_type=request.model.type,
                X_train=X_train,
                y_train=y_train,
                model_params=request.model.params,
            )
            preds = model.predict(X_test)
            fold_scores.append(pd.Series(preds, index=X_test.index, name=symbol))
            if request.direction_model is not None:
                direction_config = request.direction_model
                classifier, unavailable_reason, _ = (
                    model_service.fit_calibrated_direction_classifier(
                        model_type=direction_config.type,
                        X_train=X_train,
                        y_train=(
                            y_train > direction_config.positive_return_threshold
                        ).astype(int),
                        model_params=direction_config.params,
                        purge=purge,
                    )
                )
                if classifier is None:
                    return not_evaluated(
                        f"[{symbol}] Direction validation unavailable: "
                        f"{unavailable_reason or 'classifier was not produced.'}"
                    )
                positive_class_index = list(classifier.classes_).index(1)
                fold_probabilities.append(
                    pd.Series(
                        classifier.predict_proba(X_test)[:, positive_class_index],
                        index=X_test.index,
                        name=symbol,
                    )
                )
            for price_name in fold_prices:
                fold_prices[price_name].append(
                    data["df_model"].reindex(X_test.index)[price_name].rename(symbol)
                )

        scores = pd.concat(fold_scores, axis=1)
        price_frames = {
            name: pd.concat(series, axis=1) for name, series in fold_prices.items()
        }
        if (
            set(scores.columns) != set(request.symbols)
            or scores.shape[1] != len(request.symbols)
            or any(
                set(frame.columns) != set(request.symbols)
                or frame.shape[1] != len(request.symbols)
                for frame in price_frames.values()
            )
        ):
            return not_evaluated(
                "Validation fold does not contain the complete requested universe."
            )
        scores = scores.reindex(index=test_index, columns=request.symbols)
        price_frames = {
            name: frame.reindex(index=test_index, columns=request.symbols)
            for name, frame in price_frames.items()
        }
        values = [scores, *price_frames.values()]
        if any(
            frame.isna().any().any()
            or not all(math.isfinite(float(value)) for value in frame.to_numpy().flat)
            for frame in values
        ):
            return not_evaluated(
                "Validation fold contains missing or non-finite model/price values."
            )

        confirmation_probabilities = None
        if request.direction_model is not None:
            confirmation_probabilities = pd.concat(
                fold_probabilities, axis=1
            ).reindex(index=test_index, columns=request.symbols)
            if confirmation_probabilities.isna().any().any() or not all(
                math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
                for value in confirmation_probabilities.to_numpy().flat
            ):
                return not_evaluated(
                    "Validation direction probabilities are missing, non-finite, or "
                    "outside [0, 1]."
                )

        metrics, _, _, _ = backtest_service.run_backtest(
            scores=scores,
            open_df=price_frames["open"],
            high_df=price_frames["high"],
            low_df=price_frames["low"],
            close_df=price_frames["close"],
            strategy=strategy,
            execution=request.execution,
            market=request.market,
            return_target=request.return_target,
            confirmation_probabilities=confirmation_probabilities,
            confirmation_threshold=(
                request.direction_model.confirmation_probability_threshold
                if request.direction_model is not None
                else 0.5
            ),
        )
        if not _metrics_are_finite(metrics):
            return not_evaluated(
                "Validation backtest produced empty or non-finite metrics."
            )
        metrics_list.append(metrics)

    if not metrics_list:
        return not_evaluated(
            "Validation requested but no validation metrics were produced."
        )

    avg_metrics = {
        key: float(sum(item[key] for item in metrics_list) / len(metrics_list))
        for key in metrics_list[0].keys()
    }
    if "sharpe" in avg_metrics:
        avg_metrics["avg_sharpe"] = avg_metrics["sharpe"]
    if not _metrics_are_finite(avg_metrics):
        return not_evaluated(
            "Validation average produced empty or non-finite metrics."
        )
    return ValidationSummary(
        method=request.validation.method,
        evaluation_status="evaluated",
        metrics=avg_metrics,
    )


def execute_research_run(
    run_id: str, request: ResearchRunCreateRequest
) -> ResearchRunExecutionArtifacts:
    runtime_context = resolve_runtime_strategy(
        strategy=request.strategy,
        runtime_mode=request.runtime_mode,
        default_bundle_version=request.default_bundle_version,
    )
    foundation_context, foundation_warnings = build_run_foundation_context(request)
    resolved_strategy = runtime_context["strategy"]
    feature_config, shift_map = build_feature_config(request)
    test_size = request.validation.test_size if request.validation else 0.2
    peer_feature_map = build_run_peer_feature_map(request)
    official_no_data_dates = (
        load_official_no_data_dates(
            start_date=request.date_range.start,
            end_date=request.date_range.end,
        )
        if request.market == "TW"
        else set()
    )

    symbol_data = [
        load_symbol_data(
            run_id,
            request,
            symbol,
            feature_config,
            shift_map,
            test_size,
            peer_feature_map=peer_feature_map,
            official_no_data_dates=official_no_data_dates,
        )
        for symbol in request.symbols
    ]

    scores_df = pd.concat([item["scores"] for item in symbol_data], axis=1).sort_index()
    scores_df.index = pd.to_datetime(scores_df.index)
    confirmation_probabilities, direction_warning = (
        build_holdout_confirmation_probabilities(symbol_data, scores_df, request)
    )

    open_df = pd.concat([item["open"] for item in symbol_data], axis=1).reindex(
        scores_df.index
    )
    high_df = pd.concat([item["high"] for item in symbol_data], axis=1).reindex(
        scores_df.index
    )
    low_df = pd.concat([item["low"] for item in symbol_data], axis=1).reindex(
        scores_df.index
    )
    close_df = pd.concat([item["close"] for item in symbol_data], axis=1).reindex(
        scores_df.index
    )
    volume_df = pd.concat([item["volume"] for item in symbol_data], axis=1).reindex(
        scores_df.index
    )
    weight_kwargs = {"scores": scores_df, "strategy": resolved_strategy}
    if confirmation_probabilities is not None and request.direction_model is not None:
        weight_kwargs.update(
            confirmation_probabilities=confirmation_probabilities,
            confirmation_threshold=(
                request.direction_model.confirmation_probability_threshold
            ),
        )
    weights = backtest_service.build_target_weights(**weight_kwargs)

    metrics, equity_curve, signals, warnings = backtest_service.run_backtest(
        scores=scores_df,
        open_df=open_df,
        high_df=high_df,
        low_df=low_df,
        close_df=close_df,
        strategy=resolved_strategy,
        execution=request.execution,
        market=request.market,
        return_target=request.return_target,
        confirmation_probabilities=confirmation_probabilities,
        confirmation_threshold=(
            request.direction_model.confirmation_probability_threshold
            if request.direction_model is not None
            else 0.5
        ),
    )
    if not _metrics_are_finite(metrics):
        raise InsufficientDataError(
            "Main backtest produced empty or non-finite metrics."
        )
    forward_signals, forward_warning = build_forward_opinion_signals(
        symbol_data, request, resolved_strategy
    )
    signals.extend(forward_signals)
    if direction_warning is not None:
        warnings.append(direction_warning)
    if forward_warning is not None:
        warnings.append(forward_warning)
    warnings = [*warnings, *foundation_warnings]
    p3_summary = build_p3_summary(
        request=request,
        strategy=resolved_strategy,
        weights=weights,
        volume_df=volume_df,
    )

    baselines: dict = {}
    if request.baselines:
        close_for_baseline = close_df.reindex(scores_df.index).ffill()
        for baseline in request.baselines:
            weights = baseline_service.BASELINE_BUILDERS[baseline](close_for_baseline)
            base_metrics, _ = backtest_service.run_backtest_from_weights(
                weights=weights,
                open_df=open_df,
                high_df=high_df,
                low_df=low_df,
                close_df=close_df,
                execution=request.execution,
                market=request.market,
                return_target=request.return_target,
            )
            if not _metrics_are_finite(base_metrics):
                warnings.append(
                    f"Baseline '{baseline}' not evaluated: backtest produced "
                    "empty or non-finite metrics."
                )
                continue
            baselines[baseline] = base_metrics

    validation_summary = compute_validation_summary(
        symbol_data, request, resolved_strategy
    )
    if (
        validation_summary is not None
        and validation_summary.evaluation_status == "not_evaluated"
    ):
        warnings.append(
            f"Validation not evaluated: {validation_summary.status_reason}"
        )
    model_diagnostics = build_regression_diagnostics(symbol_data)
    version_pack = build_version_pack_payload(
        {
            "comparison_review_matrix_version": COMPARISON_REVIEW_MATRIX_VERSION,
            "scheduled_review_cadence": SCHEDULED_REVIEW_CADENCE,
            "model_family": model_service.build_model_family(request.model.type),
            "training_output_contract_version": (
                model_service.TRAINING_OUTPUT_CONTRACT_VERSION
            ),
            "adoption_comparison_policy_version": ADOPTION_COMPARISON_POLICY_VERSION,
            "threshold_policy_version": build_threshold_policy_version(
                request.return_target
            ),
            "price_basis_version": build_price_basis_version(request.return_target),
            "benchmark_comparability_gate": False,
            "comparison_eligibility": build_comparison_eligibility(
                corporate_event_state=p3_summary["corporate_event_state"],
                price_basis_version=build_price_basis_version(request.return_target),
                threshold_policy_version=build_threshold_policy_version(
                    request.return_target
                ),
                execution_cost_model_version=p3_summary["execution_cost_model_version"],
                sample_window_pending=False,
            ),
            "investability_screening_active": p3_summary[
                "investability_screening_active"
            ],
            "capacity_screening_version": p3_summary["capacity_screening_version"],
            "adv_basis_version": p3_summary["adv_basis_version"],
            "missing_feature_policy_version": p3_summary[
                "missing_feature_policy_version"
            ],
            "execution_cost_model_version": p3_summary["execution_cost_model_version"],
            "split_policy_version": build_split_policy_version(
                request.validation.method if request.validation else None
            ),
            "bootstrap_policy_version": BOOTSTRAP_POLICY_VERSION,
            "ic_overlap_policy_version": IC_OVERLAP_POLICY_VERSION,
            "factor_catalog_version": foundation_context["factor_catalog_version"],
            "external_signal_policy_version": foundation_context[
                "external_signal_policy_version"
            ],
            "external_lineage_version": foundation_context["external_lineage_version"],
            "cluster_snapshot_version": foundation_context["cluster_snapshot_version"],
            "peer_policy_version": foundation_context["peer_policy_version"],
            "peer_comparison_policy_version": foundation_context[
                "peer_comparison_policy_version"
            ],
            "execution_route": foundation_context["execution_route"],
            "simulation_profile_id": foundation_context["simulation_profile_id"],
            "simulation_adapter_version": foundation_context[
                "simulation_adapter_version"
            ],
            "live_control_profile_id": foundation_context["live_control_profile_id"],
            "live_control_version": foundation_context["live_control_version"],
            "adaptive_mode": foundation_context["adaptive_mode"],
            "adaptive_profile_id": foundation_context["adaptive_profile_id"],
            "adaptive_contract_version": foundation_context[
                "adaptive_contract_version"
            ],
            "reward_definition_version": foundation_context[
                "reward_definition_version"
            ],
            "state_definition_version": foundation_context["state_definition_version"],
            "rollout_control_version": foundation_context["rollout_control_version"],
            "scoring_factor_ids": foundation_context["scoring_factor_ids"],
        }
    )

    response = ResearchRunResponse(
        run_id=run_id,
        metrics=Metrics(**metrics),
        equity_curve=equity_curve,
        signals=signals,
        validation=validation_summary,
        model_diagnostics=model_diagnostics,
        baselines=baselines,
        warnings=warnings,
        runtime_mode=request.runtime_mode,
        default_bundle_version=runtime_context["default_bundle_version"],
        effective_strategy=EffectiveStrategyConfig(
            threshold=resolved_strategy.threshold,
            top_n=resolved_strategy.top_n,
        ),
        config_sources=ConfigSources(**runtime_context["config_sources"]),
        fallback_audit=FallbackAudit(**runtime_context["fallback_audit"]),
        tradability_state=p3_summary["tradability_state"],
        tradability_contract_version=p3_summary["tradability_contract_version"],
        capacity_screening_active=p3_summary["capacity_screening_active"],
        missing_feature_policy_state=p3_summary["missing_feature_policy_state"],
        corporate_event_state=p3_summary["corporate_event_state"],
        full_universe_count=p3_summary["full_universe_count"],
        execution_universe_count=p3_summary["execution_universe_count"],
        execution_universe_ratio=p3_summary["execution_universe_ratio"],
        liquidity_bucket_schema_version=p3_summary["liquidity_bucket_schema_version"],
        liquidity_bucket_coverages=p3_summary["liquidity_bucket_coverages"],
        stale_mark_days_with_open_positions=p3_summary[
            "stale_mark_days_with_open_positions"
        ],
        stale_risk_share=p3_summary["stale_risk_share"],
        monitor_observation_status=p3_summary["monitor_observation_status"],
        **version_pack,
    )
    factor_materializations = [
        item
        for symbol_item in symbol_data
        for item in symbol_item.get("factor_materializations", [])
    ]
    if factor_materializations:
        persist_run_factor_observations(
            run_id=run_id,
            catalog_id=foundation_context["factor_catalog_version"],
            materializations=factor_materializations,
        )
    peer_run = persist_run_peer_outputs(run_id=run_id, request=request)
    if peer_run and peer_run["warning_count"] > 0:
        warnings.append(
            f"Peer feature run emitted {peer_run['warning_count']} warning(s)."
        )
    execution_results = dispatch_run_execution_route(
        run_id=run_id,
        request=request,
        signals=signals,
    )
    if execution_results:
        warnings.append(
            f"Execution route {request.execution_route} produced {len(execution_results)} order record(s)."
        )
    if request.adaptive_mode != "off":
        record_run_adaptive_exclusion(run_id)
    response.warnings = warnings
    return ResearchRunExecutionArtifacts(
        response=response,
        runtime_context={
            **runtime_context,
            "p3_summary": p3_summary,
            "foundation_context": foundation_context,
        },
        validation_summary=validation_summary,
        warnings=warnings,
    )
