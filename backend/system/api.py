from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/health", tags=["System"])
@router.get("/api/v1/system/health", tags=["System"])
def read_health():
    return {
        "status": "ok",
        "service": "quant-platform-api",
        "version": "1.0.0",
    }
