from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException

# Use relative imports for intra-package dependencies
from . import (
    backtest_service,
    baseline_service,
    data_service,
    feature_engine,
    model_service,
    validation_service,
)
from .api_models import BacktestRequest, BacktestResponse, Metrics, ValidationSummary

# Initialize the FastAPI app
app = FastAPI(
    title="Personal Quantitative Research Platform API",
    description="An API for backtesting trading strategies.",
    version="1.0.0",
)


# --- Helpers ---
def build_feature_config(request: BacktestRequest) -> tuple[dict, dict, list[str]]:
    config: dict = {}
    shift_map: dict = {}
    warnings: list[str] = []

    if not request.features:
        raise ValueError("features must include at least one feature spec")

    for spec in request.features:
        if spec.name not in {"ma", "rsi"}:
            warnings.append(f"Feature '{spec.name}' is not supported yet.")
            continue

        config.setdefault(spec.name, []).append({"window": spec.window, "source": spec.source})
        col_name = feature_engine.feature_col_name(spec.name, spec.window, spec.source)
        shift_map[col_name] = spec.shift

    for key in ("ma", "rsi"):
        if key in config:
            unique = {(item["window"], item["source"]) for item in config[key]}
            config[key] = [{"window": w, "source": s} for w, s in sorted(unique)]

    if not config:
        raise ValueError("No supported features were provided.")

    return config, shift_map, warnings


def apply_feature_shifts(df: pd.DataFrame, shift_map: dict, warnings: list[str], symbol: str) -> None:
    for column, shift in shift_map.items():
        if column not in df.columns:
            warnings.append(f"[{symbol}] Expected feature column '{column}' not found for shift.")
            continue
        if shift:
            df[column] = df[column].shift(shift)


def compute_validation_summary(
    symbol_data: list[dict],
    request: BacktestRequest,
    warnings: list[str],
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
            warnings.append(f"[{symbol}] Validation skipped: {exc}")
            continue

        for train_range, test_range in splits:
            X_train = X.iloc[list(train_range)]
            y_train = y.iloc[list(train_range)]
            X_test = X.iloc[list(test_range)]

            if X_train.empty or X_test.empty:
                warnings.append(f"[{symbol}] Validation split has insufficient data.")
                continue

            model = model_service.fit_xgboost_regressor(X_train, y_train, request.model.params)
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
                selection=request.selection,
                trading_rules=request.trading_rules,
                exit_rules=request.exit_rules,
                execution=request.execution,
                market=request.market,
                return_target=request.return_target,
            )
            metrics_list.append(metrics)

    if not metrics_list:
        return None

    avg_metrics = {}
    for key in metrics_list[0].keys():
        avg_metrics[key] = float(sum(item[key] for item in metrics_list) / len(metrics_list))

    return ValidationSummary(method=request.validation.method, metrics=avg_metrics)


# --- API Endpoints ---
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Quant Platform API. Visit /docs for documentation."}


@app.post("/api/v1/backtest", tags=["Backtesting"], response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRequest) -> BacktestResponse:
    """
    Runs a complete backtest for a given stock, date range, and feature configuration.
    """
    try:
        warnings: list[str] = []

        if request.model.type != "xgboost":
            raise HTTPException(status_code=400, detail="Only xgboost model type is supported.")

        feature_config, shift_map, feature_warnings = build_feature_config(request)
        warnings.extend(feature_warnings)

        scores_list = []
        open_list = []
        high_list = []
        low_list = []
        close_list = []
        symbol_data: list[dict] = []

        test_size = request.validation.test_size if request.validation else 0.2

        for symbol in request.symbols:
            df = data_service.get_data(
                symbols=symbol,
                start_date=request.date_range.start,
                end_date=request.date_range.end,
                market=request.market,
            )
            if df.empty:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for symbol '{symbol}' in the specified date range.",
                )

            df_features = feature_engine.add_features(df.copy(), feature_config)
            apply_feature_shifts(df_features, shift_map, warnings, symbol)

            df_model, X, y = model_service.prepare_training_data(
                df_features,
                return_target=request.return_target,
                horizon_days=request.horizon_days,
            )

            X_train, X_test, y_train, y_test = model_service.time_series_split(X, y, test_size=test_size)
            model = model_service.fit_xgboost_regressor(X_train, y_train, request.model.params)
            preds = model.predict(X_test)

            scores = pd.Series(preds, index=X_test.index, name=symbol)
            scores_list.append(scores)
            open_list.append(df_model.loc[X_test.index, "open"].rename(symbol))
            high_list.append(df_model.loc[X_test.index, "high"].rename(symbol))
            low_list.append(df_model.loc[X_test.index, "low"].rename(symbol))
            close_list.append(df_model.loc[X_test.index, "close"].rename(symbol))

            symbol_data.append(
                {
                    "symbol": symbol,
                    "df_model": df_model,
                    "X": X,
                    "y": y,
                }
            )

        if not scores_list:
            raise HTTPException(status_code=400, detail="No predictions available for backtest.")

        scores_df = pd.concat(scores_list, axis=1).sort_index()
        scores_df.index = pd.to_datetime(scores_df.index)

        open_df = pd.concat(open_list, axis=1).reindex(scores_df.index)
        high_df = pd.concat(high_list, axis=1).reindex(scores_df.index)
        low_df = pd.concat(low_list, axis=1).reindex(scores_df.index)
        close_df = pd.concat(close_list, axis=1).reindex(scores_df.index)

        metrics, equity_curve, signals, bt_warnings = backtest_service.run_backtest(
            scores=scores_df,
            open_df=open_df,
            high_df=high_df,
            low_df=low_df,
            close_df=close_df,
            selection=request.selection,
            trading_rules=request.trading_rules,
            exit_rules=request.exit_rules,
            execution=request.execution,
            market=request.market,
            return_target=request.return_target,
        )
        warnings.extend(bt_warnings)

        baselines: dict = {}
        if request.baselines:
            close_for_baseline = close_df.reindex(scores_df.index).ffill()
            for baseline in request.baselines:
                builder = baseline_service.BASELINE_BUILDERS.get(baseline)
                if not builder:
                    warnings.append(f"Unknown baseline '{baseline}' was skipped.")
                    continue
                weights = builder(close_for_baseline)
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

        validation_summary = compute_validation_summary(symbol_data, request, warnings)

        return BacktestResponse(
            run_id=str(uuid4()),
            metrics=Metrics(**metrics),
            equity_curve=equity_curve,
            signals=signals,
            validation=validation_summary,
            baselines=baselines,
            warnings=warnings,
        )

    except ValueError as ve:
        # Catch specific value errors, e.g., not enough data for a train/test split
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Catch any other unexpected errors during the process
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


# To run this API locally:
# uvicorn backend.main:app --reload
