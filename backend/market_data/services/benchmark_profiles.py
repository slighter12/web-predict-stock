from __future__ import annotations

import logging

from backend.market_data.contracts.operations import BenchmarkProfileRequest
from backend.market_data.repositories.benchmark_profiles import (
    get_benchmark_profile,
    list_benchmark_profiles,
    persist_benchmark_profile,
)
from backend.market_data.services._normalization import clean_required_text

logger = logging.getLogger(__name__)


def create_benchmark_profile(request: BenchmarkProfileRequest) -> dict:
    profile_id = clean_required_text(request.id)
    if not profile_id:
        raise ValueError("Benchmark profile ID must not be empty.")
    payload = {
        "id": profile_id,
        "cpu_class": clean_required_text(request.cpu_class),
        "memory_size": clean_required_text(request.memory_size),
        "storage_type": clean_required_text(request.storage_type),
        "compression_settings": clean_required_text(request.compression_settings),
        "archive_layout_version": clean_required_text(request.archive_layout_version),
        "network_class": clean_required_text(request.network_class),
    }
    logger.info("Creating benchmark profile benchmark_profile_id=%s", payload["id"])
    return persist_benchmark_profile(payload)


def read_benchmark_profile(profile_id: str) -> dict:
    return get_benchmark_profile(profile_id)


def list_registered_benchmark_profiles(limit: int = 50) -> list[dict]:
    return list_benchmark_profiles(limit=limit)


def assert_benchmark_profile_exists(profile_id: str | None) -> None:
    if profile_id is None:
        return
    read_benchmark_profile(profile_id)
