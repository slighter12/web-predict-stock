from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from ..repositories.tick_archive_repository import (
    list_recent_tick_archive_trading_dates,
    list_tick_archive_objects_for_dates,
    list_tick_restore_runs_for_dates,
)

TICK_KPI_TRADING_DAY_WINDOW = 20
TICK_BENCHMARK_MAX_COMPRESSED_GB_PER_DAY = 5.0
_SUCCEEDED_STATUS = "succeeded"
_MIN_VALID_ELAPSED_SECONDS = 1e-6


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * percentile
    lower_index = math.floor(index)
    upper_index = math.ceil(index)
    if lower_index == upper_index:
        return float(sorted_values[lower_index])
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return float(lower_value + (upper_value - lower_value) * (index - lower_index))


def _metric(
    *,
    value: float | None,
    status: str,
    window: str,
    numerator: float | None = None,
    denominator: float | None = None,
    unit: str | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "value": value,
        "status": status,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
        "window": window,
        "details": details or {},
    }


def _bytes_to_gb(value: int | float) -> float:
    return float(value) / (1024**3)


def _build_archive_day_totals(
    archive_objects: list[dict[str, Any]],
) -> dict[date, dict[str, float]]:
    day_totals: dict[date, dict[str, float]] = defaultdict(
        lambda: {
            "compressed_bytes": 0.0,
            "uncompressed_bytes": 0.0,
            "object_count": 0.0,
        }
    )
    for item in archive_objects:
        trading_date = item.get("trading_date")
        if trading_date is None:
            continue
        totals = day_totals[trading_date]
        totals["compressed_bytes"] += float(item.get("compressed_bytes") or 0)
        totals["uncompressed_bytes"] += float(item.get("uncompressed_bytes") or 0)
        totals["object_count"] += 1.0
    return dict(day_totals)


def _select_latest_archive_run_objects(
    archive_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for item in archive_objects:
        trading_date = item.get("trading_date")
        if trading_date is not None:
            grouped_by_date[trading_date].append(item)

    latest_run_keys: dict[date, tuple[Any, Any, Any]] = {}
    latest_run_ids: dict[date, int] = {}
    selected_objects: list[dict[str, Any]] = []

    for trading_date, items in grouped_by_date.items():
        if any(item.get("run_id") is None for item in items):
            selected_objects.extend(items)
            continue
        for item in items:
            run_id = item.get("run_id")
            candidate_key = (
                item.get("run_completed_at")
                or item.get("run_created_at")
                or item.get("created_at")
                or datetime.min.replace(tzinfo=timezone.utc),
                int(run_id),
                int(item.get("id") or 0),
            )
            current_key = latest_run_keys.get(trading_date)
            if current_key is None or candidate_key > current_key:
                latest_run_keys[trading_date] = candidate_key
                latest_run_ids[trading_date] = int(run_id)

        selected_objects.extend(
            item
            for item in items
            if item.get("run_id") == latest_run_ids.get(trading_date)
        )

    return selected_objects


def _eligible_benchmark_day_totals(
    archive_day_totals: dict[date, dict[str, float]],
) -> dict[date, dict[str, float]]:
    max_compressed_bytes = TICK_BENCHMARK_MAX_COMPRESSED_GB_PER_DAY * (1024**3)
    return {
        trading_date: totals
        for trading_date, totals in archive_day_totals.items()
        if 0 < totals["compressed_bytes"] <= max_compressed_bytes
    }


def _build_benchmark_windows(
    restore_runs: list[dict[str, Any]],
    eligible_day_totals: dict[date, dict[str, float]],
    eligible_archive_object_ids: set[int],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[date, str], dict[str, Any]] = {}
    seen_archive_objects: set[tuple[date, str, int]] = set()

    for run in restore_runs:
        trading_date = run.get("trading_date")
        benchmark_profile_id = run.get("benchmark_profile_id")
        if trading_date not in eligible_day_totals or benchmark_profile_id is None:
            continue
        archive_object_id = run.get("archive_object_id")
        if archive_object_id is None:
            continue
        if eligible_archive_object_ids and int(archive_object_id) not in eligible_archive_object_ids:
            continue
        archive_object_key = (trading_date, benchmark_profile_id, int(archive_object_id))
        if archive_object_key in seen_archive_objects:
            continue
        seen_archive_objects.add(archive_object_key)
        group_key = (trading_date, benchmark_profile_id)
        bucket = grouped.setdefault(
            group_key,
            {
                "trading_date": trading_date,
                "benchmark_profile_id": benchmark_profile_id,
                "compressed_bytes": 0.0,
                "elapsed_seconds_sum": 0.0,
                "max_elapsed_seconds": 0.0,
                "run_count": 0,
                "archive_object_ids": [],
                "restore_started_at_min": None,
                "restore_completed_at_max": None,
            },
        )
        bucket["compressed_bytes"] += float(run.get("compressed_bytes") or 0)
        elapsed_seconds = float(run.get("elapsed_seconds") or 0.0)
        bucket["elapsed_seconds_sum"] += elapsed_seconds
        bucket["max_elapsed_seconds"] = max(bucket["max_elapsed_seconds"], elapsed_seconds)
        bucket["run_count"] += 1
        bucket["archive_object_ids"].append(int(archive_object_id))
        restore_started_at = run.get("restore_started_at")
        restore_completed_at = run.get("restore_completed_at")
        if restore_started_at is not None and (
            bucket["restore_started_at_min"] is None
            or restore_started_at < bucket["restore_started_at_min"]
        ):
            bucket["restore_started_at_min"] = restore_started_at
        if restore_completed_at is not None and (
            bucket["restore_completed_at_max"] is None
            or restore_completed_at > bucket["restore_completed_at_max"]
        ):
            bucket["restore_completed_at_max"] = restore_completed_at

    eligible_windows: list[dict[str, Any]] = []
    for bucket in grouped.values():
        trading_date = bucket["trading_date"]
        required_day_total = eligible_day_totals[trading_date]["compressed_bytes"]
        if bucket["compressed_bytes"] + 1e-6 < required_day_total:
            continue
        elapsed_seconds = None
        if (
            bucket["restore_started_at_min"] is not None
            and bucket["restore_completed_at_max"] is not None
        ):
            window_elapsed_seconds = (
                bucket["restore_completed_at_max"] - bucket["restore_started_at_min"]
            ).total_seconds()
            if window_elapsed_seconds > _MIN_VALID_ELAPSED_SECONDS:
                elapsed_seconds = window_elapsed_seconds
        throughput = (
            _bytes_to_gb(bucket["compressed_bytes"]) / (elapsed_seconds / 60)
            if bucket["compressed_bytes"] > 0
            and elapsed_seconds is not None
            else None
        )
        eligible_windows.append(
            {
                **bucket,
                "required_compressed_bytes": required_day_total,
                "elapsed_seconds": elapsed_seconds,
                "throughput_gb_per_minute": throughput,
                "archive_object_count": len(bucket["archive_object_ids"]),
            }
        )

    eligible_windows.sort(
        key=lambda item: (item["trading_date"], item["benchmark_profile_id"])
    )
    return eligible_windows


def get_tick_ops_kpi_summary() -> dict:
    trading_dates = list_recent_tick_archive_trading_dates(
        limit=TICK_KPI_TRADING_DAY_WINDOW,
        statuses=[_SUCCEEDED_STATUS],
    )
    archive_objects = list_tick_archive_objects_for_dates(
        trading_dates,
        run_statuses=[_SUCCEEDED_STATUS],
    )
    latest_archive_run_objects = _select_latest_archive_run_objects(archive_objects)
    restore_runs = list_tick_restore_runs_for_dates(
        trading_dates,
        benchmark_only=True,
        archive_run_statuses=[_SUCCEEDED_STATUS],
        restore_statuses=[_SUCCEEDED_STATUS],
    )

    archive_day_totals = _build_archive_day_totals(latest_archive_run_objects)
    eligible_day_totals = _eligible_benchmark_day_totals(archive_day_totals)
    benchmark_windows = _build_benchmark_windows(
        restore_runs,
        eligible_day_totals,
        {
            int(item["id"])
            for item in latest_archive_run_objects
            if item.get("id") is not None
        },
    )

    compressed_total = sum(item["compressed_bytes"] for item in archive_objects)
    uncompressed_total = sum(item["uncompressed_bytes"] for item in archive_objects)
    compression_target = (
        max(0.0, 1 - (compressed_total / uncompressed_total)) * 100
        if uncompressed_total > 0
        else None
    )
    metric_001 = _metric(
        value=compression_target,
        status="pass"
        if compression_target is not None and compression_target >= 50.0
        else "fail",
        numerator=float(uncompressed_total - compressed_total)
        if uncompressed_total > 0
        else None,
        denominator=float(uncompressed_total) if uncompressed_total > 0 else None,
        unit="percent",
        window=f"rolling {TICK_KPI_TRADING_DAY_WINDOW} succeeded trading days",
        details={
            "sample_count": len(archive_objects),
            "trading_day_count": len(trading_dates),
            "successful_archive_only": True,
        },
    )

    restore_minutes = [
        item["elapsed_seconds"] / 60
        for item in benchmark_windows
        if item.get("elapsed_seconds") is not None
    ]
    latency_p95 = _percentile(restore_minutes, 0.95)
    metric_002 = _metric(
        value=latency_p95,
        status="pass" if latency_p95 is not None and latency_p95 < 30 else "fail",
        denominator=float(len(restore_minutes)) if restore_minutes else None,
        unit="minutes",
        window="rolling 20 succeeded trading days, benchmark windows <= 5 compressed GB/day",
        details={
            "sample_count": len(restore_minutes),
            "eligible_trading_day_count": len(eligible_day_totals),
            "eligible_window_count": len(benchmark_windows),
            "successful_archive_only": True,
            "successful_restore_only": True,
            "benchmark_profile_required": True,
        },
    )

    throughput_values = [
        float(item["throughput_gb_per_minute"])
        for item in benchmark_windows
        if item.get("throughput_gb_per_minute") is not None
    ]
    metric_003 = _metric(
        value=_percentile(throughput_values, 0.50),
        status="pass" if throughput_values else "fail",
        denominator=float(len(throughput_values)) if throughput_values else None,
        unit="gb_per_minute",
        window="rolling 20 succeeded trading days, benchmark windows <= 5 compressed GB/day",
        details={
            "sample_count": len(throughput_values),
            "eligible_trading_day_count": len(eligible_day_totals),
            "eligible_window_count": len(benchmark_windows),
            "p50": _percentile(throughput_values, 0.50),
            "p95": _percentile(throughput_values, 0.95),
            "successful_archive_only": True,
            "successful_restore_only": True,
            "benchmark_profile_required": True,
        },
    )

    metrics = {
        "KPI-TICK-001": metric_001,
        "KPI-TICK-002": metric_002,
        "KPI-TICK-003": metric_003,
    }
    overall_status = (
        "pass"
        if all(metric["status"] == "pass" for metric in metrics.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P2-OPS-001",
        "overall_status": overall_status,
        "metrics": metrics,
        "binding_status": "exploratory",
        "binding_reason": "TBD-002 remains open; KPI-TICK-* must not be treated as durable binding gate evidence.",
        "selection_policy": {
            "successful_archive_run_statuses": [_SUCCEEDED_STATUS],
            "successful_restore_statuses": [_SUCCEEDED_STATUS],
            "benchmark_profile_required": True,
            "max_compressed_gb_per_trading_day": TICK_BENCHMARK_MAX_COMPRESSED_GB_PER_DAY,
            "window_trading_days": TICK_KPI_TRADING_DAY_WINDOW,
            "benchmark_window_scope": "latest succeeded archive run per trading_date and benchmark_profile_id",
            "full_day_restore_required": True,
            "restore_time_model": "window_wall_clock",
        },
    }
