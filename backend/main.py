import logging
import os
from contextvars import ContextVar
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (
    backtest_service,
    baseline_service,
    data_service,
    feature_engine,
    model_service,
    validation_service,
)
from .api_models import (
    BacktestRequest,
    BacktestResponse,
    ConfigSources,
    EffectiveStrategyConfig,
    FallbackAudit,
    Metrics,
    ValidationSummary,
)
from .errors import (
    BacktestError,
    DataAccessError,
    DataNotFoundError,
    InsufficientDataError,
    UnsupportedConfigurationError,
)
from .strategy_service import (
    COMPARISON_ELIGIBILITY,
    ResearchStrategyConfig,
    build_threshold_policy_version,
    build_price_basis_version,
    resolve_runtime_strategy,
)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

app = FastAPI(
    title="Personal Quantitative Research Platform API",
    description="Backend API for quantitative research and backtesting.",
    version="1.0.0",
)


def _parse_cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


def _error_payload(
    request_id: str,
    code: str,
    message: str,
    details: dict | None = None,
) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
        },
        "meta": {
            "request_id": request_id,
        },
    }
    if details:
        payload["error"]["details"] = details
    return payload


def _error_response(
    status_code: int,
    request_id: str,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(request_id=request_id, code=code, message=message, details=details),
        headers={"X-Request-Id": request_id},
    )


def _backtest_error_code(exc: BacktestError) -> str:
    if isinstance(exc, DataNotFoundError):
        return "RESOURCE_NOT_FOUND"
    if isinstance(exc, InsufficientDataError):
        return "INSUFFICIENT_DATA"
    if isinstance(exc, UnsupportedConfigurationError):
        return "UNSUPPORTED_CONFIGURATION"
    return "BACKTEST_REQUEST_REJECTED"


def _http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "RESOURCE_NOT_FOUND"
    if status_code == 405:
        return "METHOD_NOT_ALLOWED"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "PERMISSION_DENIED"
    return "HTTP_ERROR"


def _http_error_message(status_code: int, detail: object) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if status_code == 404:
        return "找不到指定資源。"
    if status_code == 405:
        return "不支援此 HTTP 方法。"
    if status_code == 401:
        return "尚未通過驗證。"
    if status_code == 403:
        return "沒有執行此操作的權限。"
    return "請求失敗。"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", request_id_var.get())


def _validation_error_details(exc: RequestValidationError) -> dict:
    fields: list[dict] = []
    for error in exc.errors():
        location = [str(item) for item in error.get("loc", []) if item != "body"]
        fields.append(
            {
                "field": ".".join(location) if location else "request",
                "code": error.get("type", "invalid"),
                "reason": error.get("msg", "Invalid value"),
            }
        )
    return {"fields": fields}


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid4().hex}"
    token = request_id_var.set(request_id)
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(BacktestError)
async def handle_backtest_error(request: Request, exc: BacktestError):
    request_id = _request_id(request)
    logger.warning(
        "Backtest request rejected request_id=%s path=%s code=%s detail=%s",
        request_id,
        request.url.path,
        _backtest_error_code(exc),
        exc,
    )
    return _error_response(
        status_code=exc.status_code,
        request_id=request_id,
        code=_backtest_error_code(exc),
        message=str(exc),
    )


@app.exception_handler(DataAccessError)
async def handle_data_access_error(request: Request, exc: DataAccessError):
    request_id = _request_id(request)
    logger.exception(
        "Database access failure request_id=%s path=%s",
        request_id,
        request.url.path,
    )
    return _error_response(
        status_code=500,
        request_id=request_id,
        code="DATA_ACCESS_FAILED",
        message="資料存取失敗，請稍後再試。",
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    request_id = _request_id(request)
    logger.warning(
        "Validation failed request_id=%s path=%s errors=%s",
        request_id,
        request.url.path,
        exc.errors(),
    )
    return _error_response(
        status_code=422,
        request_id=request_id,
        code="VALIDATION_FAILED",
        message="請檢查輸入內容。",
        details=_validation_error_details(exc),
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError):
    request_id = _request_id(request)
    logger.warning(
        "Value error request_id=%s path=%s detail=%s",
        request_id,
        request.url.path,
        exc,
    )
    return _error_response(
        status_code=400,
        request_id=request_id,
        code="VALIDATION_FAILED",
        message=str(exc),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    request_id = _request_id(request)
    logger.warning(
        "HTTP error request_id=%s path=%s status=%s detail=%s",
        request_id,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return _error_response(
        status_code=exc.status_code,
        request_id=request_id,
        code=_http_error_code(exc.status_code),
        message=_http_error_message(exc.status_code, exc.detail),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    request_id = _request_id(request)
    logger.exception(
        "Unexpected error request_id=%s path=%s",
        request_id,
        request.url.path,
    )
    return _error_response(
        status_code=500,
        request_id=request_id,
        code="INTERNAL_SERVER_ERROR",
        message="伺服器發生未預期錯誤。",
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
                strategy=strategy,
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


@app.get("/api/v1/health", tags=["Health"])
def read_health():
    return {
        "status": "ok",
        "service": "quant-platform-api",
        "version": app.version,
    }


@app.post("/api/v1/backtest", tags=["Backtesting"], response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRequest) -> BacktestResponse:
    logger.info(
        "Backtest request received request_id=%s strategy=%s market=%s symbols=%s",
        request_id_var.get(),
        request.strategy.type,
        request.market,
        request.symbols,
    )
    runtime_context = resolve_runtime_strategy(
        strategy=request.strategy,
        runtime_mode=request.runtime_mode,
        default_bundle_version=request.default_bundle_version,
    )
    resolved_strategy = runtime_context["strategy"]
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
        strategy=resolved_strategy,
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

    validation_summary = compute_validation_summary(symbol_data, request, resolved_strategy)
    logger.info(
        "Backtest request completed request_id=%s strategy=%s market=%s symbols=%s warnings=%s",
        request_id_var.get(),
        resolved_strategy.type,
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
        runtime_mode=request.runtime_mode,
        default_bundle_version=runtime_context["default_bundle_version"],
        effective_strategy=EffectiveStrategyConfig(
            threshold=resolved_strategy.threshold,
            top_n=resolved_strategy.top_n,
        ),
        config_sources=ConfigSources(**runtime_context["config_sources"]),
        fallback_audit=FallbackAudit(**runtime_context["fallback_audit"]),
        threshold_policy_version=build_threshold_policy_version(request.return_target),
        price_basis_version=build_price_basis_version(request.return_target),
        benchmark_comparability_gate=False,
        comparison_eligibility=COMPARISON_ELIGIBILITY,
    )


# To run this API locally:
# uvicorn backend.main:app --reload
