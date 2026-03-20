from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from ..database import BenchmarkProfile, SessionLocal
from ..errors import DataAccessError, DataNotFoundError
from ._shared import normalize_created_at

logger = logging.getLogger(__name__)


def _benchmark_profile_row_to_dict(row: BenchmarkProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "cpu_class": row.cpu_class,
        "memory_size": row.memory_size,
        "storage_type": row.storage_type,
        "compression_settings": row.compression_settings,
        "archive_layout_version": row.archive_layout_version,
        "network_class": row.network_class,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_benchmark_profile(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(BenchmarkProfile, payload["id"]) or BenchmarkProfile(
                id=payload["id"]
            )
            row.cpu_class = payload["cpu_class"]
            row.memory_size = payload["memory_size"]
            row.storage_type = payload["storage_type"]
            row.compression_settings = payload["compression_settings"]
            row.archive_layout_version = payload["archive_layout_version"]
            row.network_class = payload["network_class"]
            session.add(row)
            session.commit()
            session.refresh(row)
            return _benchmark_profile_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist benchmark profile benchmark_profile_id=%s",
            payload["id"],
        )
        raise DataAccessError("Failed to persist benchmark profile.") from exc


def get_benchmark_profile(profile_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(BenchmarkProfile, profile_id)
            if row is None:
                raise DataNotFoundError(
                    f"Benchmark profile '{profile_id}' was not found."
                )
            return _benchmark_profile_row_to_dict(row)
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to load benchmark profile benchmark_profile_id=%s", profile_id
        )
        raise DataAccessError("Failed to load benchmark profile.") from exc


def list_benchmark_profiles(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(BenchmarkProfile)
                .order_by(desc(BenchmarkProfile.created_at), BenchmarkProfile.id)
                .limit(limit)
            )
            return [
                _benchmark_profile_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list benchmark profiles from DB")
        raise DataAccessError("Failed to list benchmark profiles.") from exc
