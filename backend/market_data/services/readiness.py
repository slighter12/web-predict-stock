from __future__ import annotations

import bisect
import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from backend.database import DailyOHLCV, RawIngestAudit, SessionLocal
from backend.market_data.contracts.operations import TwDailyReadinessRequest
from backend.platform.errors import DataAccessError
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue
        if symbol in seen:
            raise ValueError("symbols must not contain duplicates")
        seen.add(symbol)
        normalized.append(symbol)
    if not normalized:
        raise ValueError("symbols must contain at least one non-empty symbol")
    return normalized


def _stale_trading_days(
    all_market_days: list[date], latest_symbol_date: date | None
) -> int:
    if latest_symbol_date is None or not all_market_days:
        return 0
    idx = bisect.bisect_right(all_market_days, latest_symbol_date)
    return max(len(all_market_days) - idx, 0)


def _weekday_dates(start: date, end: date) -> list[date]:
    current = start
    days: list[date] = []
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _coerce_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def summarize_tw_daily_readiness(request: TwDailyReadinessRequest) -> dict:
    symbols = _normalize_symbols(request.symbols)
    date_range = request.date_range

    try:
        with SessionLocal() as session:
            latest_market_date = _coerce_date(
                session.execute(
                    select(func.max(DailyOHLCV.date)).where(DailyOHLCV.market == "TW")
                ).scalar_one_or_none()
            )

            latest_daily_rows = session.execute(
                select(DailyOHLCV.symbol, func.max(DailyOHLCV.date))
                .where(DailyOHLCV.market == "TW")
                .where(DailyOHLCV.symbol.in_(symbols))
                .group_by(DailyOHLCV.symbol)
            ).all()
            latest_daily_by_symbol = {
                symbol: normalized_latest_date
                for symbol, latest_date in latest_daily_rows
                if (normalized_latest_date := _coerce_date(latest_date)) is not None
            }

            latest_raw_rows = session.execute(
                select(RawIngestAudit.symbol, func.max(RawIngestAudit.fetch_timestamp))
                .where(RawIngestAudit.market == "TW")
                .where(RawIngestAudit.symbol.in_(symbols))
                .where(RawIngestAudit.fetch_status == "success")
                .group_by(RawIngestAudit.symbol)
            ).all()
            latest_raw_by_symbol = {
                symbol: latest_fetch_ts
                for symbol, latest_fetch_ts in latest_raw_rows
                if latest_fetch_ts is not None
            }

            all_market_days = (
                [
                    normalized_item
                    for item in session.execute(
                        select(func.distinct(DailyOHLCV.date))
                        .where(DailyOHLCV.market == "TW")
                        .order_by(DailyOHLCV.date)
                    )
                    .scalars()
                    .all()
                    if (normalized_item := _coerce_date(item)) is not None
                ]
                if latest_market_date is not None
                else []
            )

            requested_trading_days: list[date] | None = None
            coverage_by_symbol: dict[str, int] = {}
            if date_range is not None:
                requested_trading_days = _weekday_dates(
                    date_range.start, date_range.end
                )
                coverage_rows = session.execute(
                    select(DailyOHLCV.symbol, func.count(func.distinct(DailyOHLCV.date)))
                    .where(DailyOHLCV.market == "TW")
                    .where(DailyOHLCV.symbol.in_(symbols))
                    .where(DailyOHLCV.date >= date_range.start)
                    .where(DailyOHLCV.date <= date_range.end)
                    .group_by(DailyOHLCV.symbol)
                ).all()
                coverage_by_symbol = {
                    symbol: int(covered_days or 0)
                    for symbol, covered_days in coverage_rows
                }
    except Exception as exc:
        logger.exception(
            "Failed to summarize TW daily readiness symbols=%s range=%s",
            symbols,
            date_range,
        )
        raise DataAccessError("Failed to summarize TW daily readiness.") from exc

    requested_count = (
        len(requested_trading_days) if requested_trading_days is not None else None
    )
    symbol_summaries: list[dict] = []
    summary = {"ready": 0, "warning": 0, "missing": 0, "stale": 0}

    for symbol in symbols:
        latest_daily_date = latest_daily_by_symbol.get(symbol)
        latest_raw_fetch_ts = latest_raw_by_symbol.get(symbol)
        stale_trading_days = _stale_trading_days(all_market_days, latest_daily_date)
        covered_trading_days = (
            coverage_by_symbol.get(symbol, 0) if requested_count is not None else None
        )
        missing_trading_days = (
            max(requested_count - (covered_trading_days or 0), 0)
            if requested_count is not None
            else None
        )

        warnings: list[str] = []
        if latest_daily_date is None:
            warnings.append("No TW daily rows found for the requested symbol.")
        if requested_count is not None:
            if requested_count == 0:
                warnings.append("No TW trading days found in the requested date range.")
            elif (covered_trading_days or 0) == 0:
                warnings.append("No TW daily rows cover the requested date range.")
            elif (missing_trading_days or 0) > 0:
                warnings.append(
                    f"Missing {missing_trading_days} of {requested_count} requested trading days."
                )
        if stale_trading_days > 0 and latest_market_date is not None:
            warnings.append(
                f"Latest daily row is {stale_trading_days} trading day(s) behind {latest_market_date.isoformat()}."
            )

        if latest_daily_date is None or (
            requested_count not in (None, 0) and (covered_trading_days or 0) == 0
        ):
            status = "missing"
        elif warnings:
            status = "warning"
        else:
            status = "ready"

        summary[status] += 1
        if stale_trading_days > 0:
            summary["stale"] += 1

        symbol_summaries.append(
            {
                "symbol": symbol,
                "status": status,
                "latest_daily_date": latest_daily_date,
                "latest_raw_fetch_ts": latest_raw_fetch_ts,
                "requested_trading_days": requested_count,
                "covered_trading_days": covered_trading_days,
                "missing_trading_days": missing_trading_days,
                "stale_trading_days": stale_trading_days,
                "warnings": warnings,
            }
        )

    overall_status = (
        "missing"
        if summary["missing"] > 0
        else "warning"
        if summary["warning"] > 0
        else "ready"
    )
    return {
        "market": "TW",
        "overall_status": overall_status,
        "evaluated_at": utc_now(),
        "date_range": date_range.model_dump() if date_range is not None else None,
        "summary": summary,
        "symbols": symbol_summaries,
    }
