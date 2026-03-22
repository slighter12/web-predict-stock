from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from backend.database import (
    DailyOHLCV,
    ImportantEvent,
    IngestionWatchlist,
    NormalizedReplayRun,
    RecoveryDrill,
    RecoveryDrillSchedule,
    ScheduledIngestionAttempt,
    ScheduledIngestionRun,
    SessionLocal,
    SymbolLifecycleRecord,
)
from backend.market_data.repositories.raw_ingest import list_market_trading_days
from backend.market_data.services._schedule_slots import resolve_schedule_slot_date
from backend.platform.errors import DataAccessError
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)
_ACTIVE_LIFECYCLE_EVENTS = {"listing", "re_listing"}
_RECOVERABLE_TIMESTAMP_CLASSES = {"official_exchange", "official_issuer"}


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


def _latest_market_date(market: str, reference_date: date) -> date:
    trading_days = list_market_trading_days(
        market,
        end_date=reference_date,
        descending=True,
        limit=1,
    )
    return trading_days[0] if trading_days else reference_date


def _iter_month_dates(start_date: date, end_date: date) -> list[tuple[int, int]]:
    year = start_date.year
    month = start_date.month
    items: list[tuple[int, int]] = []
    while (year, month) <= (end_date.year, end_date.month):
        items.append((year, month))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return items


def _calculate_kpi_data_001_and_002(reference_date: date) -> tuple[dict, dict]:
    trading_days = list_market_trading_days(
        "TW",
        end_date=reference_date,
        descending=True,
        limit=20,
    )
    if not trading_days:
        empty_metric = _metric(
            value=None, status="fail", window="rolling 20 trading days"
        )
        return empty_metric, empty_metric

    window_days = set(trading_days)
    start_date = min(window_days)
    watchlists: list[IngestionWatchlist]
    runs: list[ScheduledIngestionRun]
    attempts: list[ScheduledIngestionAttempt]

    try:
        with SessionLocal() as session:
            watchlists = (
                session.execute(
                    select(IngestionWatchlist).where(
                        IngestionWatchlist.is_active.is_(True),
                        IngestionWatchlist.market == "TW",
                    )
                )
                .scalars()
                .all()
            )
            runs = (
                session.execute(
                    select(ScheduledIngestionRun).where(
                        ScheduledIngestionRun.market == "TW",
                        ScheduledIngestionRun.scheduled_for_date >= start_date,
                        ScheduledIngestionRun.scheduled_for_date <= max(window_days),
                    )
                )
                .scalars()
                .all()
            )
            run_ids = [row.id for row in runs]
            attempts = (
                session.execute(
                    select(ScheduledIngestionAttempt).where(
                        ScheduledIngestionAttempt.run_id.in_(run_ids)
                    )
                )
                .scalars()
                .all()
                if run_ids
                else []
            )
    except Exception as exc:
        logger.exception("Failed to calculate KPI-DATA-001 and KPI-DATA-002")
        raise DataAccessError("Failed to calculate operational KPIs.") from exc

    runs_by_slot = {
        (row.watchlist_id, row.scheduled_for_date): row
        for row in runs
        if row.scheduled_for_date in window_days
    }
    attempts_by_run: dict[int, list[ScheduledIngestionAttempt]] = {}
    for attempt in attempts:
        attempts_by_run.setdefault(attempt.run_id, []).append(attempt)
    for items in attempts_by_run.values():
        items.sort(key=lambda item: item.attempt_number)

    denominator = 0
    first_attempt_success_count = 0
    retry_adjusted_success_count = 0

    for watchlist in watchlists:
        watchlist_created_date = (
            watchlist.created_at.date()
            if watchlist.created_at is not None
            else reference_date
        )
        for trading_day in window_days:
            if watchlist_created_date > trading_day:
                continue
            denominator += 1
            run = runs_by_slot.get((watchlist.id, trading_day))
            if run is None:
                continue
            slot_attempts = attempts_by_run.get(run.id, [])
            if slot_attempts and slot_attempts[0].status == "succeeded":
                first_attempt_success_count += 1
            if any(item.status == "succeeded" for item in slot_attempts):
                retry_adjusted_success_count += 1

    value_001 = (
        (first_attempt_success_count / denominator * 100) if denominator else None
    )
    value_002 = (
        retry_adjusted_success_count / denominator * 100 if denominator else None
    )
    return (
        _metric(
            value=value_001,
            status="pass"
            if denominator and value_001 is not None and value_001 >= 99.0
            else "fail",
            numerator=float(first_attempt_success_count),
            denominator=float(denominator),
            unit="percent",
            window="rolling 20 trading days",
        ),
        _metric(
            value=value_002,
            status="pass"
            if denominator and value_002 is not None and value_002 >= 99.5
            else "fail",
            numerator=float(retry_adjusted_success_count),
            denominator=float(denominator),
            unit="percent",
            window="rolling 20 trading days",
        ),
    )


def _resolve_symbol_active_window(
    lifecycle_rows: list[SymbolLifecycleRecord],
    month_start: date,
    month_end: date,
) -> tuple[date | None, date | None]:
    is_active = True
    active_start = month_start
    sorted_rows = sorted(lifecycle_rows, key=lambda item: item.effective_date)

    for row in sorted_rows:
        if row.effective_date < month_start:
            if row.event_type in _ACTIVE_LIFECYCLE_EVENTS:
                is_active = True
            elif row.event_type == "delisting":
                is_active = False

    if not is_active:
        relisting = next(
            (
                row
                for row in sorted_rows
                if month_start <= row.effective_date <= month_end
                and row.event_type in _ACTIVE_LIFECYCLE_EVENTS
            ),
            None,
        )
        if relisting is None:
            return None, None
        active_start = max(month_start, relisting.effective_date)

    delisting = next(
        (
            row
            for row in sorted_rows
            if active_start <= row.effective_date <= month_end
            and row.event_type == "delisting"
        ),
        None,
    )
    active_end = (
        month_end if delisting is None else delisting.effective_date - timedelta(days=1)
    )
    if active_end < active_start:
        return None, None
    return active_start, active_end


def _calculate_kpi_data_003(reference_date: date) -> dict:
    latest_market_date = _latest_market_date("TW", reference_date)
    month_start = latest_market_date.replace(day=1)
    if latest_market_date.month == 12:
        month_end = date(latest_market_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(
            latest_market_date.year, latest_market_date.month + 1, 1
        ) - timedelta(days=1)
    trading_days = list_market_trading_days(
        "TW",
        start_date=month_start,
        end_date=month_end,
    )
    try:
        with SessionLocal() as session:
            watchlists = (
                session.execute(
                    select(IngestionWatchlist).where(
                        IngestionWatchlist.is_active.is_(True),
                        IngestionWatchlist.market == "TW",
                    )
                )
                .scalars()
                .all()
            )
            watchlist_symbols = [watchlist.symbol for watchlist in watchlists]
            lifecycle_rows = (
                session.execute(
                    select(SymbolLifecycleRecord).where(
                        SymbolLifecycleRecord.market == "TW",
                        SymbolLifecycleRecord.symbol.in_(watchlist_symbols),
                        SymbolLifecycleRecord.effective_date <= month_end,
                    )
                )
                .scalars()
                .all()
                if watchlist_symbols
                else []
            )
            actual_rows = (
                session.execute(
                    select(DailyOHLCV.symbol, DailyOHLCV.date).where(
                        DailyOHLCV.market == "TW",
                        DailyOHLCV.symbol.in_(watchlist_symbols),
                        DailyOHLCV.date >= month_start,
                        DailyOHLCV.date <= latest_market_date,
                    )
                ).all()
                if watchlist_symbols
                else []
            )
    except Exception as exc:
        logger.exception("Failed to load data for KPI-DATA-003")
        raise DataAccessError("Failed to calculate operational KPIs.") from exc

    lifecycle_by_symbol: dict[str, list[SymbolLifecycleRecord]] = {}
    for row in lifecycle_rows:
        lifecycle_by_symbol.setdefault(row.symbol, []).append(row)
    actual_days_by_symbol: dict[str, set[date]] = {}
    for symbol, actual_date in actual_rows:
        actual_days_by_symbol.setdefault(symbol, set()).add(actual_date)

    completeness_values: list[float] = []
    for watchlist in watchlists:
        active_start, active_end = _resolve_symbol_active_window(
            lifecycle_by_symbol.get(watchlist.symbol, []),
            month_start,
            latest_market_date,
        )
        if active_start is None or active_end is None:
            continue
        expected_days = [
            day for day in trading_days if active_start <= day <= active_end
        ]
        if not expected_days:
            continue
        actual_days = {
            actual_date
            for actual_date in actual_days_by_symbol.get(watchlist.symbol, set())
            if active_start <= actual_date <= active_end
        }
        completeness_values.append(len(actual_days) / len(expected_days))

    if not completeness_values:
        return _metric(
            value=None,
            status="fail",
            window=f"monthly:{month_start.isoformat()}",
            details={"active_symbol_count": 0},
        )

    passing_count = sum(1 for value in completeness_values if value >= 0.95)
    active_symbol_count = len(completeness_values)
    passing_ratio = passing_count / active_symbol_count
    return _metric(
        value=passing_ratio * 100,
        status="pass" if passing_ratio >= 0.95 else "fail",
        numerator=float(passing_count),
        denominator=float(active_symbol_count),
        unit="percent",
        window=f"monthly:{month_start.isoformat()}",
        details={
            "active_symbol_count": active_symbol_count,
            "passing_symbol_count": passing_count,
            "passing_symbol_ratio": passing_ratio,
            "p50": _percentile(completeness_values, 0.50),
            "p05": _percentile(completeness_values, 0.05),
        },
    )


def _calculate_kpi_data_004(reference_date: date) -> dict:
    start_date = reference_date - timedelta(days=89)
    try:
        with SessionLocal() as session:
            rows = (
                session.execute(
                    select(RecoveryDrill).where(
                        RecoveryDrill.created_at
                        >= datetime.combine(
                            start_date, datetime.min.time(), tzinfo=timezone.utc
                        )
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        logger.exception("Failed to load recovery drills for KPI-DATA-004")
        raise DataAccessError("Failed to calculate operational KPIs.") from exc
    deltas = [
        int(row.completed_trading_day_delta)
        for row in rows
        if row.completed_trading_day_delta is not None
    ]
    value = max(deltas) if deltas else None
    return _metric(
        value=float(value) if value is not None else None,
        status="pass" if deltas and value is not None and value <= 1 else "fail",
        unit="trading_days",
        window="rolling 90 calendar days",
        numerator=float(len([delta for delta in deltas if delta <= 1]))
        if deltas
        else None,
        denominator=float(len(deltas)) if deltas else None,
    )


def _calculate_kpi_data_005(reference_date: date) -> dict:
    start_date = reference_date - timedelta(days=89)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    durations_hours: list[float] = []
    try:
        with SessionLocal() as session:
            replay_rows = (
                session.execute(
                    select(NormalizedReplayRun).where(
                        NormalizedReplayRun.benchmark_profile_id.is_not(None),
                        NormalizedReplayRun.replay_completed_at.is_not(None),
                        NormalizedReplayRun.created_at >= start_dt,
                    )
                )
                .scalars()
                .all()
            )
            recovery_rows = (
                session.execute(
                    select(RecoveryDrill).where(
                        RecoveryDrill.benchmark_profile_id.is_not(None),
                        RecoveryDrill.drill_completed_at.is_not(None),
                        RecoveryDrill.created_at >= start_dt,
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        logger.exception(
            "Failed to load replay and recovery telemetry for KPI-DATA-005"
        )
        raise DataAccessError("Failed to calculate operational KPIs.") from exc

    for row in replay_rows:
        elapsed = row.replay_completed_at - row.replay_started_at
        durations_hours.append(elapsed.total_seconds() / 3600)
    for row in recovery_rows:
        elapsed = row.drill_completed_at - row.drill_started_at
        durations_hours.append(elapsed.total_seconds() / 3600)

    p95 = _percentile(durations_hours, 0.95)
    return _metric(
        value=p95,
        status="pass" if p95 is not None and p95 < 4 else "fail",
        unit="hours",
        window="rolling 90 calendar days",
        denominator=float(len(durations_hours)) if durations_hours else None,
        details={"sample_count": len(durations_hours)},
    )


def _calculate_kpi_data_006_and_008(reference_date: date) -> tuple[dict, dict]:
    start_date = reference_date - timedelta(days=89)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    try:
        with SessionLocal() as session:
            rows = (
                session.execute(
                    select(ImportantEvent).where(
                        ImportantEvent.created_at >= start_dt,
                        ImportantEvent.timestamp_source_class.in_(
                            _RECOVERABLE_TIMESTAMP_CLASSES
                        ),
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        logger.exception(
            "Failed to load important events for KPI-DATA-006 and KPI-DATA-008"
        )
        raise DataAccessError("Failed to calculate operational KPIs.") from exc

    recovery_windows = [
        max(0.0, (row.created_at - row.event_publication_ts).total_seconds() / 3600)
        for row in rows
        if row.created_at is not None and row.event_publication_ts is not None
    ]
    sample_count = len(recovery_windows)
    metric_008 = _metric(
        value=float(sample_count),
        status="pass" if sample_count >= 5 else "insufficient_sample",
        unit="events",
        window="rolling 90 calendar days",
        numerator=float(sample_count),
        denominator=5.0,
    )
    max_hours = max(recovery_windows) if recovery_windows else None
    metric_006 = _metric(
        value=max_hours,
        status=(
            "insufficient_sample"
            if sample_count < 5
            else "pass"
            if max_hours is not None and max_hours <= 24
            else "fail"
        ),
        unit="hours",
        window="rolling 90 calendar days",
        numerator=float(sample_count),
        denominator=float(sample_count) if sample_count else None,
        details={
            "sample_count": sample_count,
            "average_hours": (
                sum(recovery_windows) / sample_count if sample_count else None
            ),
        },
    )
    return metric_006, metric_008


def _calculate_kpi_data_007(reference_date: date) -> dict:
    start_date = reference_date - timedelta(days=89)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    due_slots: set[tuple[int, date]] = set()
    try:
        with SessionLocal() as session:
            schedules = (
                session.execute(
                    select(RecoveryDrillSchedule).where(
                        RecoveryDrillSchedule.is_active.is_(True),
                        RecoveryDrillSchedule.created_at
                        <= datetime.combine(
                            reference_date, datetime.max.time(), tzinfo=timezone.utc
                        ),
                    )
                )
                .scalars()
                .all()
            )
            recovery_rows = (
                session.execute(
                    select(RecoveryDrill).where(
                        RecoveryDrill.schedule_id.is_not(None),
                        RecoveryDrill.scheduled_for_date >= start_date,
                        RecoveryDrill.scheduled_for_date <= reference_date,
                        RecoveryDrill.created_at >= start_dt,
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        logger.exception("Failed to load recovery schedules for KPI-DATA-007")
        raise DataAccessError("Failed to calculate operational KPIs.") from exc

    for schedule in schedules:
        created_date = (
            schedule.created_at.date()
            if schedule.created_at is not None
            else reference_date
        )
        slot_start = max(start_date, created_date)
        for year, month in _iter_month_dates(slot_start, reference_date):
            slot_date = resolve_schedule_slot_date(year, month, schedule.day_of_month)
            if slot_start <= slot_date <= reference_date:
                due_slots.add((schedule.id, slot_date))

    covered_slots = {
        (row.schedule_id, row.scheduled_for_date)
        for row in recovery_rows
        if row.schedule_id is not None and row.scheduled_for_date is not None
    }
    denominator = len(due_slots)
    numerator = len(due_slots & covered_slots)
    value = (numerator / denominator * 100) if denominator else None
    return _metric(
        value=value,
        status="pass" if denominator >= 1 and numerator == denominator else "fail",
        numerator=float(numerator),
        denominator=float(denominator),
        unit="percent",
        window="rolling 90 calendar days",
    )


def get_ops_kpi_summary(reference_time: datetime | None = None) -> dict:
    current_time = reference_time or utc_now()
    reference_date = current_time.date()
    metric_001, metric_002 = _calculate_kpi_data_001_and_002(reference_date)
    metric_003 = _calculate_kpi_data_003(reference_date)
    metric_004 = _calculate_kpi_data_004(reference_date)
    metric_005 = _calculate_kpi_data_005(reference_date)
    metric_006, metric_008 = _calculate_kpi_data_006_and_008(reference_date)
    metric_007 = _calculate_kpi_data_007(reference_date)

    metrics = {
        "KPI-DATA-001": metric_001,
        "KPI-DATA-002": metric_002,
        "KPI-DATA-003": metric_003,
        "KPI-DATA-004": metric_004,
        "KPI-DATA-005": metric_005,
        "KPI-DATA-006": metric_006,
        "KPI-DATA-007": metric_007,
        "KPI-DATA-008": metric_008,
    }
    gate_ready = all(
        metrics[key]["status"] == "pass"
        for key in (
            "KPI-DATA-001",
            "KPI-DATA-002",
            "KPI-DATA-003",
            "KPI-DATA-004",
            "KPI-DATA-005",
            "KPI-DATA-007",
        )
    ) and (
        metric_006["status"] == "pass"
        or (
            metric_006["status"] == "insufficient_sample"
            and metric_008["status"] == "insufficient_sample"
        )
    )
    return {
        "gate_id": "GATE-P1-OPS-001",
        "overall_status": "pass" if gate_ready else "fail",
        "metrics": metrics,
    }
