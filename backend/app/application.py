from __future__ import annotations

import logging
import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.execution.api import router as execution_router
from backend.market_data.api import router as market_data_router
from backend.platform.errors import BacktestError, DataAccessError
from backend.platform.http.errors import (
    build_error_response,
    http_error_code,
    http_error_message,
    research_run_error_code,
    validation_error_details,
)
from backend.platform.http.request_context import (
    clear_request_run_id,
    ensure_request_run_id,
    get_request_id,
    get_request_run_id,
    mark_request_research_run_persist_attempted,
    mark_request_research_run_persisted,
    request_id_var,
    request_research_run_persist_attempted,
)
from backend.platform.http.request_payload import read_request_payload
from backend.research.api import router as research_router
from backend.research.services.registry import (
    record_unexpected_failure,
    record_validation_failure,
)
from backend.signals.api import router as signals_router
from backend.system.api import router as system_router

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TW Daily Quant ML Research Workbench API",
    description="Public v1 API for TW daily baseline research, experiment review, and data readiness operations.",
    version="1.0.0",
)


def _parse_cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

app.include_router(system_router)
app.include_router(research_router)
app.include_router(market_data_router)
app.include_router(signals_router)
app.include_router(execution_router)


@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Quant research backend is running. Visit /docs for API documentation."
    }


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
async def handle_research_run_error(request: Request, exc: BacktestError):
    current_request_id = get_request_id(request)
    logger.warning(
        "Research run rejected request_id=%s path=%s code=%s detail=%s",
        current_request_id,
        request.url.path,
        research_run_error_code(exc),
        exc,
    )
    return build_error_response(
        status_code=exc.status_code,
        request_id=current_request_id,
        code=research_run_error_code(exc),
        message=str(exc),
        run_id=get_request_run_id(request),
    )


@app.exception_handler(DataAccessError)
async def handle_data_access_error(request: Request, exc: DataAccessError):
    current_request_id = get_request_id(request)
    logger.exception(
        "Database access failure request_id=%s path=%s",
        current_request_id,
        request.url.path,
    )
    return build_error_response(
        status_code=500,
        request_id=current_request_id,
        code="DATA_ACCESS_FAILED",
        message="資料存取失敗，請稍後再試。",
        run_id=get_request_run_id(request),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
):
    current_request_id = get_request_id(request)
    run_id = ensure_request_run_id(request)
    if (
        request.url.path == "/api/v1/research/runs"
        and not request_research_run_persist_attempted(request)
    ):
        payload = await read_request_payload(request)
        mark_request_research_run_persist_attempted(request)
        try:
            from backend import app as app_module

            app_module.record_validation_failure(
                run_id=run_id,
                request_id=current_request_id,
                request_payload=payload,
                details=validation_error_details(exc),
            )
        except DataAccessError:
            clear_request_run_id(request)
            logger.exception(
                "Failed to record validation failure request_id=%s run_id=%s",
                current_request_id,
                run_id,
            )
        else:
            mark_request_research_run_persisted(request)
        run_id = get_request_run_id(request)
    return build_error_response(
        status_code=422,
        request_id=current_request_id,
        code="VALIDATION_FAILED",
        message="請檢查輸入內容。",
        details=validation_error_details(exc),
        run_id=run_id,
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError):
    current_request_id = get_request_id(request)
    logger.warning(
        "Value error request_id=%s path=%s detail=%s",
        current_request_id,
        request.url.path,
        exc,
    )
    return build_error_response(
        status_code=400,
        request_id=current_request_id,
        code="VALIDATION_FAILED",
        message=str(exc),
        run_id=get_request_run_id(request),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    current_request_id = get_request_id(request)
    logger.warning(
        "HTTP error request_id=%s path=%s status=%s detail=%s",
        current_request_id,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return build_error_response(
        status_code=exc.status_code,
        request_id=current_request_id,
        code=http_error_code(exc.status_code),
        message=http_error_message(exc.status_code, exc.detail),
        run_id=get_request_run_id(request),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    current_request_id = get_request_id(request)
    run_id = get_request_run_id(request)
    if (
        request.url.path == "/api/v1/research/runs"
        and not request_research_run_persist_attempted(request)
    ):
        payload = await read_request_payload(request)
        if run_id is None:
            run_id = ensure_request_run_id(request)
        mark_request_research_run_persist_attempted(request)
        try:
            from backend import app as app_module

            app_module.record_unexpected_failure(
                run_id=run_id,
                request_id=current_request_id,
                request_payload=payload,
                rejection_reason="伺服器發生未預期錯誤。",
            )
        except DataAccessError:
            clear_request_run_id(request)
            logger.exception(
                "Failed to record unexpected failure request_id=%s run_id=%s",
                current_request_id,
                run_id,
            )
        else:
            mark_request_research_run_persisted(request)
        run_id = get_request_run_id(request)
    logger.exception(
        "Unexpected error request_id=%s path=%s", current_request_id, request.url.path
    )
    return build_error_response(
        status_code=500,
        request_id=current_request_id,
        code="INTERNAL_SERVER_ERROR",
        message="伺服器發生未預期錯誤。",
        run_id=run_id,
    )
