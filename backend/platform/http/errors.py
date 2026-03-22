from __future__ import annotations

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.platform.errors import (
    BacktestError,
    DataNotFoundError,
    ExternalFetchError,
    InsufficientDataError,
    UnsupportedConfigurationError,
)


def build_error_payload(
    request_id: str,
    code: str,
    message: str,
    details: dict | None = None,
    run_id: str | None = None,
) -> dict:
    payload = {
        "error": {"code": code, "message": message},
        "meta": {"request_id": request_id},
    }
    if run_id:
        payload["meta"]["run_id"] = run_id
    if details:
        payload["error"]["details"] = details
    return payload


def build_error_response(
    status_code: int,
    request_id: str,
    code: str,
    message: str,
    details: dict | None = None,
    run_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            request_id=request_id,
            code=code,
            message=message,
            details=details,
            run_id=run_id,
        ),
        headers={"X-Request-Id": request_id},
    )


def research_run_error_code(exc: BacktestError) -> str:
    if isinstance(exc, DataNotFoundError):
        return "RESOURCE_NOT_FOUND"
    if isinstance(exc, ExternalFetchError):
        return "EXTERNAL_FETCH_FAILED"
    if isinstance(exc, InsufficientDataError):
        return "INSUFFICIENT_DATA"
    if isinstance(exc, UnsupportedConfigurationError):
        return "UNSUPPORTED_CONFIGURATION"
    return "RESEARCH_RUN_REJECTED"


def http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "RESOURCE_NOT_FOUND"
    if status_code == 405:
        return "METHOD_NOT_ALLOWED"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "PERMISSION_DENIED"
    return "HTTP_ERROR"


def http_error_message(status_code: int, detail: object) -> str:
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


def validation_error_details(exc: RequestValidationError) -> dict:
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
