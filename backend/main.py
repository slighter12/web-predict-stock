import logging
import os
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException

from . import (
    backtest_service,
    baseline_service,
    data_service,
    feature_engine,
    model_service,
    validation_service,
)
from .api_models import BacktestRequest, BacktestResponse, Metrics, ValidationSummary
from .errors import (
    BacktestError,
    DataAccessError,
    DataNotFoundError,
    InsufficientDataError,
    UnsupportedConfigurationError,
)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Personal Quantitative Research Platform API",
    description="Backend API for quantitative research and backtesting.",
    version="1.0.0",
)


def build_feature_config(request: BacktestRequest) -> tuple[dict, dict]:
    config: dict = {}
    shift_map: dict = {}

    if not request.features:
        raise UnsupportedConfigurationError("features must include at least one feature spec.")

    for spec in request.features:
        config.setdefault(spec.name, []).append({"window": spec.window, "source": spec.source})
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


def _load_symbol_data(
    request: BacktestRequest,
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
        X_train, X_test, y_train, _ = model_service.time_series_split(X, y, test_size=test_size)
    except ValueError as exc:
        raise InsufficientDataError(f"[{symbol}] {exc}") from exc

    model = model_service.fit_xgboost_regressor(X_train, y_train, request.model.params)
    preds = model.predict(X_test)

    logger.info(
        "Prepared symbol=%s rows=%s features=%s train=%s test=%s",
        symbol,
        len(df_model),
        list(X.columns),
        len(X_train),
        len(X_test),
    )

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
    }


def compute_validation_summary(
    symbol_data: list[dict],
    request: BacktestRequest,
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
            raise InsufficientDataError(f"[{symbol}] Validation cannot run: {exc}") from exc

        for train_range, test_range in splits:
            X_train = X.iloc[list(train_range)]
            y_train = y.iloc[list(train_range)]
            X_test = X.iloc[list(test_range)]

            if X_train.empty or X_test.empty:
                raise InsufficientDataError(f"[{symbol}] Validation split has insufficient data.")

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
                strategy=request.strategy,
                execution=request.execution,
                market=request.market,
                return_target=request.return_target,
            )
            metrics_list.append(metrics)

    if not metrics_list:
        raise InsufficientDataError("Validation requested but no validation metrics were produced.")

    avg_metrics = {}
    for key in metrics_list[0].keys():
        avg_metrics[key] = float(sum(item[key] for item in metrics_list) / len(metrics_list))
    if "sharpe" in avg_metrics:
        avg_metrics["avg_sharpe"] = avg_metrics["sharpe"]

    logger.info(
        "Validation completed method=%s splits=%s symbols=%s",
        request.validation.method,
        request.validation.splits,
        len(symbol_data),
    )
    return ValidationSummary(method=request.validation.method, metrics=avg_metrics)


@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Quant research backend is running. Visit /docs for API documentation."}


@app.post("/api/v1/backtest", tags=["Backtesting"], response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRequest) -> BacktestResponse:
    logger.info(
        "Backtest request received strategy=%s market=%s symbols=%s",
        request.strategy.type,
        request.market,
        request.symbols,
    )
    try:
        feature_config, shift_map = build_feature_config(request)
        test_size = request.validation.test_size if request.validation else 0.2

        symbol_data = [
            _load_symbol_data(request, symbol, feature_config, shift_map, test_size)
            for symbol in request.symbols
        ]

        scores_df = pd.concat([item["scores"] for item in symbol_data], axis=1).sort_index()
        scores_df.index = pd.to_datetime(scores_df.index)

        open_df = pd.concat([item["open"] for item in symbol_data], axis=1).reindex(scores_df.index)
        high_df = pd.concat([item["high"] for item in symbol_data], axis=1).reindex(scores_df.index)
        low_df = pd.concat([item["low"] for item in symbol_data], axis=1).reindex(scores_df.index)
        close_df = pd.concat([item["close"] for item in symbol_data], axis=1).reindex(scores_df.index)

        metrics, equity_curve, signals, warnings = backtest_service.run_backtest(
            scores=scores_df,
            open_df=open_df,
            high_df=high_df,
            low_df=low_df,
            close_df=close_df,
            strategy=request.strategy,
            execution=request.execution,
            market=request.market,
            return_target=request.return_target,
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

        validation_summary = compute_validation_summary(symbol_data, request)
        logger.info(
            "Backtest request completed strategy=%s market=%s symbols=%s warnings=%s",
            request.strategy.type,
            request.market,
            request.symbols,
            len(warnings),
        )
        return BacktestResponse(
            run_id=str(uuid4()),
            metrics=Metrics(**metrics),
            equity_curve=equity_curve,
            signals=signals,
            validation=validation_summary,
            baselines=baselines,
            warnings=warnings,
        )
    except BacktestError as exc:
        logger.warning("Backtest request rejected: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except DataAccessError as exc:
        logger.exception("Database access failure during backtest request")
        raise HTTPException(status_code=500, detail="Database access failed.") from exc
    except ValueError as exc:
        logger.warning("Backtest request invalid: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during backtest request")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc


# To run this API locally:
# uvicorn backend.main:app --reload
