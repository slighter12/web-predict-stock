from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from .. import (
    backtest_service,
    baseline_service,
    data_service,
    feature_engine,
    model_service,
    validation_service,
)
from ..domain.runtime_bundle import build_version_pack_payload
from ..errors import (
    DataNotFoundError,
    InsufficientDataError,
    UnsupportedConfigurationError,
)
from ..schemas.research_runs import (
    Metrics,
    ResearchRunCreateRequest,
    ResearchRunResponse,
    ValidationSummary,
)
from ..schemas.runtime import ConfigSources, EffectiveStrategyConfig, FallbackAudit
from ..services.p3_screening_service import build_p3_summary
from ..strategy_service import (
    ADOPTION_COMPARISON_POLICY_VERSION,
    BOOTSTRAP_POLICY_VERSION,
    COMPARISON_REVIEW_MATRIX_VERSION,
    IC_OVERLAP_POLICY_VERSION,
    ResearchStrategyConfig,
    SCHEDULED_REVIEW_CADENCE,
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

    for key in ("ma", "rsi"):
        if key in config:
            unique = {(item["window"], item["source"]) for item in config[key]}
            config[key] = [{"window": w, "source": s} for w, s in sorted(unique)]

    return config, shift_map


def apply_feature_shifts(df: pd.DataFrame, shift_map: dict, symbol: str) -> None:
    for column, shift in shift_map.items():
        if column not in df.columns:
            raise UnsupportedConfigurationError(
                f"[{symbol}] Expected feature column '{column}' not found after feature generation."
            )
        if shift:
            df[column] = df[column].shift(shift)


def load_symbol_data(
    request: ResearchRunCreateRequest,
    symbol: str,
    feature_config: dict,
    shift_map: dict,
    test_size: float,
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

    df_features = feature_engine.add_features(df.copy(), feature_config)
    apply_feature_shifts(df_features, shift_map, symbol)

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
        X_train, X_test, y_train, _ = model_service.time_series_split(
            X, y, test_size=test_size
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

    return {
        "symbol": symbol,
        "df_model": df_model,
        "X": X,
        "y": y,
        "scores": pd.Series(preds, index=X_test.index, name=symbol),
        "open": df_model.loc[X_test.index, "open"].rename(symbol),
        "high": df_model.loc[X_test.index, "high"].rename(symbol),
        "low": df_model.loc[X_test.index, "low"].rename(symbol),
        "close": df_model.loc[X_test.index, "close"].rename(symbol),
        "volume": df_model.loc[X_test.index, "volume"].rename(symbol),
    }


def compute_validation_summary(
    symbol_data: list[dict],
    request: ResearchRunCreateRequest,
    strategy: ResearchStrategyConfig,
) -> ValidationSummary | None:
    if request.validation is None:
        return None

    metrics_list: list[dict] = []
    for data in symbol_data:
        symbol = data["symbol"]
        df_model = data["df_model"]
        X = data["X"]
        y = data["y"]

        try:
            splits = validation_service.generate_splits(
                length=len(X),
                method=request.validation.method,
                splits=request.validation.splits,
                test_size=request.validation.test_size,
            )
        except ValueError as exc:
            raise InsufficientDataError(
                f"[{symbol}] Validation cannot run: {exc}"
            ) from exc

        for train_range, test_range in splits:
            X_train = X.iloc[list(train_range)]
            y_train = y.iloc[list(train_range)]
            X_test = X.iloc[list(test_range)]

            if X_train.empty or X_test.empty:
                raise InsufficientDataError(
                    f"[{symbol}] Validation split has insufficient data."
                )

            model = model_service.fit_regressor(
                model_type=request.model.type,
                X_train=X_train,
                y_train=y_train,
                model_params=request.model.params,
            )
            preds = model.predict(X_test)
            scores = pd.DataFrame({symbol: preds}, index=X_test.index)
            open_df = df_model.loc[X_test.index, "open"].to_frame(symbol)
            high_df = df_model.loc[X_test.index, "high"].to_frame(symbol)
            low_df = df_model.loc[X_test.index, "low"].to_frame(symbol)
            close_df = df_model.loc[X_test.index, "close"].to_frame(symbol)
            metrics, _, _, _ = backtest_service.run_backtest(
                scores=scores,
                open_df=open_df,
                high_df=high_df,
                low_df=low_df,
                close_df=close_df,
                strategy=strategy,
                execution=request.execution,
                market=request.market,
                return_target=request.return_target,
            )
            metrics_list.append(metrics)

    if not metrics_list:
        raise InsufficientDataError(
            "Validation requested but no validation metrics were produced."
        )

    avg_metrics = {
        key: float(sum(item[key] for item in metrics_list) / len(metrics_list))
        for key in metrics_list[0].keys()
    }
    if "sharpe" in avg_metrics:
        avg_metrics["avg_sharpe"] = avg_metrics["sharpe"]
    return ValidationSummary(method=request.validation.method, metrics=avg_metrics)


def execute_research_run(
    run_id: str, request: ResearchRunCreateRequest
) -> ResearchRunExecutionArtifacts:
    runtime_context = resolve_runtime_strategy(
        strategy=request.strategy,
        runtime_mode=request.runtime_mode,
        default_bundle_version=request.default_bundle_version,
    )
    resolved_strategy = runtime_context["strategy"]
    feature_config, shift_map = build_feature_config(request)
    test_size = request.validation.test_size if request.validation else 0.2

    symbol_data = [
        load_symbol_data(request, symbol, feature_config, shift_map, test_size)
        for symbol in request.symbols
    ]

    scores_df = pd.concat([item["scores"] for item in symbol_data], axis=1).sort_index()
    scores_df.index = pd.to_datetime(scores_df.index)

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
    weights = backtest_service.build_target_weights(
        scores=scores_df,
        strategy=resolved_strategy,
    )

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
    )
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
            baselines[baseline] = base_metrics

    validation_summary = compute_validation_summary(
        symbol_data, request, resolved_strategy
    )
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
        }
    )

    response = ResearchRunResponse(
        run_id=run_id,
        metrics=Metrics(**metrics),
        equity_curve=equity_curve,
        signals=signals,
        validation=validation_summary,
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
    return ResearchRunExecutionArtifacts(
        response=response,
        runtime_context={
            **runtime_context,
            "p3_summary": p3_summary,
        },
        validation_summary=validation_summary,
        warnings=warnings,
    )
