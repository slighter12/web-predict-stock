from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select

from backend.database import MicrostructureObservation, SessionLocal
from backend.platform.errors import DataAccessError
from backend.platform.db.repository_helpers import json_loads
from backend.research.services.tradability import LIQUIDITY_BUCKET_SCHEMA_VERSION, MONITOR_PROFILE_ID

ACTIVE_WINDOW_DAYS = 20
BASELINE_WINDOW_DAYS = 60
MIN_BASELINE_DAYS = 40


def _metric(
    *,
    value: float | None,
    status: str,
    window: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "status": status,
        "numerator": None,
        "denominator": None,
        "unit": None,
        "window": window,
        "details": details or {},
    }


def _relative_drift(active_avg: float, baseline_avg: float) -> float:
    return abs(active_avg - baseline_avg) / max(baseline_avg, 0.01)


def _load_recent_observations(market: str) -> list[MicrostructureObservation]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(MicrostructureObservation)
                .where(
                    MicrostructureObservation.monitor_profile_id == MONITOR_PROFILE_ID
                )
                .where(MicrostructureObservation.market == market)
                .order_by(
                    desc(MicrostructureObservation.trading_date),
                    desc(MicrostructureObservation.id),
                )
                .limit(ACTIVE_WINDOW_DAYS + BASELINE_WINDOW_DAYS)
            )
            rows = session.execute(stmt).scalars().all()
    except Exception as exc:
        raise DataAccessError("Failed to load microstructure observations.") from exc

    return list(reversed(rows))


def get_micro_kpi_summary(market: str = "TW") -> dict:
    observations = _load_recent_observations(market)
    active = observations[-ACTIVE_WINDOW_DAYS:]
    baseline = observations[: max(0, len(observations) - len(active))]
    baseline = baseline[-BASELINE_WINDOW_DAYS:]

    if len(active) < ACTIVE_WINDOW_DAYS or len(baseline) < MIN_BASELINE_DAYS:
        return {
            "gate_id": "GATE-P3-OPS-001",
            "overall_status": "insufficient_sample",
            "metrics": {
                "KPI-MICRO-001": _metric(
                    value=None,
                    status="insufficient_sample",
                    window="20 active trading days + 60 baseline trading days",
                    details={
                        "active_observation_count": len(active),
                        "baseline_observation_count": len(baseline),
                    },
                ),
                "KPI-MICRO-002": _metric(
                    value=None,
                    status="insufficient_sample",
                    window="per required bucket over 20 active + 60 baseline trading days",
                    details={
                        "required_bucket_count": 0,
                        "active_observation_count": len(active),
                        "baseline_observation_count": len(baseline),
                    },
                ),
                "KPI-MICRO-003": _metric(
                    value=None,
                    status="insufficient_sample",
                    window="20 active trading days + 60 baseline trading days",
                    details={
                        "active_observation_count": len(active),
                        "baseline_observation_count": len(baseline),
                    },
                ),
            },
            "selection_policy": {
                "monitor_profile_id": MONITOR_PROFILE_ID,
                "market": market,
                "liquidity_bucket_schema_version": LIQUIDITY_BUCKET_SCHEMA_VERSION,
            },
            "binding_status": "bootstrap_only",
            "binding_reason": "Baseline window has fewer than 40 valid trading-day observations.",
        }

    active_ratio_avg = sum(item.execution_universe_ratio for item in active) / len(
        active
    )
    baseline_ratio_avg = sum(item.execution_universe_ratio for item in baseline) / len(
        baseline
    )
    ratio_drift = _relative_drift(active_ratio_avg, baseline_ratio_avg)
    ratio_status = "pass" if ratio_drift <= 0.10 else "fail"

    active_bucket_coverages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    baseline_bucket_coverages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in active:
        for coverage in json_loads(item.bucket_coverages_json, []):
            active_bucket_coverages[coverage["bucket_key"]].append(coverage)
    for item in baseline:
        for coverage in json_loads(item.bucket_coverages_json, []):
            baseline_bucket_coverages[coverage["bucket_key"]].append(coverage)

    required_buckets: list[str] = []
    bucket_results: dict[str, Any] = {}
    for bucket_key, rows in baseline_bucket_coverages.items():
        baseline_full_share = sum(row["full_universe_ratio"] for row in rows) / len(
            rows
        )
        if baseline_full_share < 0.05:
            continue
        required_buckets.append(bucket_key)
        baseline_coverage_avg = sum(
            row["execution_coverage_ratio"] for row in rows
        ) / len(rows)
        active_rows = active_bucket_coverages.get(bucket_key, [])
        active_coverage_avg = (
            sum(row["execution_coverage_ratio"] for row in active_rows)
            / len(active_rows)
            if active_rows
            else 0.0
        )
        bucket_drift = _relative_drift(active_coverage_avg, baseline_coverage_avg)
        bucket_results[bucket_key] = {
            "active_avg": active_coverage_avg,
            "baseline_avg": baseline_coverage_avg,
            "drift": bucket_drift,
            "status": "pass" if bucket_drift <= 0.10 else "fail",
            "baseline_full_universe_ratio": baseline_full_share,
        }

    bucket_status = (
        "pass"
        if required_buckets
        and all(result["status"] == "pass" for result in bucket_results.values())
        else ("fail" if required_buckets else "insufficient_sample")
    )

    active_stale_share = sum(
        1.0 if item.stale_mark_with_open_positions else 0.0 for item in active
    ) / len(active)
    baseline_stale_share = sum(
        1.0 if item.stale_mark_with_open_positions else 0.0 for item in baseline
    ) / len(baseline)
    stale_drift = _relative_drift(active_stale_share, baseline_stale_share)
    stale_status = (
        "pass" if active_stale_share <= 0.05 and stale_drift <= 0.20 else "fail"
    )

    overall_status = "pass"
    if any(status != "pass" for status in (ratio_status, bucket_status, stale_status)):
        overall_status = "fail"

    return {
        "gate_id": "GATE-P3-OPS-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-MICRO-001": _metric(
                value=active_ratio_avg,
                status=ratio_status,
                window="20 active trading days + 60 baseline trading days",
                details={
                    "active_20d_avg": active_ratio_avg,
                    "baseline_60d_avg": baseline_ratio_avg,
                    "relative_drift": ratio_drift,
                },
            ),
            "KPI-MICRO-002": _metric(
                value=float(
                    max(
                        (result["drift"] for result in bucket_results.values()),
                        default=0.0,
                    )
                ),
                status=bucket_status,
                window="per required bucket over 20 active + 60 baseline trading days",
                details={
                    "required_bucket_count": len(required_buckets),
                    "required_buckets": bucket_results,
                },
            ),
            "KPI-MICRO-003": _metric(
                value=active_stale_share,
                status=stale_status,
                window="20 active trading days + 60 baseline trading days",
                details={
                    "active_stale_risk_share": active_stale_share,
                    "baseline_60d_avg_stale_risk_share": baseline_stale_share,
                    "relative_drift": stale_drift,
                },
            ),
        },
        "selection_policy": {
            "monitor_profile_id": MONITOR_PROFILE_ID,
            "market": market,
            "liquidity_bucket_schema_version": LIQUIDITY_BUCKET_SCHEMA_VERSION,
            "active_window_days": ACTIVE_WINDOW_DAYS,
            "baseline_window_days": BASELINE_WINDOW_DAYS,
        },
        "binding_status": "bootstrap_only"
        if overall_status == "insufficient_sample"
        else "monitoring",
        "binding_reason": None
        if overall_status != "insufficient_sample"
        else "Baseline window has fewer than 40 valid trading-day observations.",
    }
