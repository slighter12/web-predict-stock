from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from numbers import Integral
from typing import Any

import pandas as pd

from backend.market_data.domain import official_daily
from backend.market_data.repositories import daily_bars as daily_bars_repository
from backend.market_data.repositories import official_audits as official_audits_repository
from backend.market_data.services.company_profiles import list_active_tw_company_profiles

logger = logging.getLogger(__name__)

TW_TIMEZONE = official_daily.TW_TIMEZONE
OFFICIAL_SOURCES = official_daily.OFFICIAL_SOURCES
_BATCH_SOURCES = (
    official_daily.SOURCE_TWSE_MI_INDEX,
    official_daily.SOURCE_TPEX_AFTERTRADING_OTC,
)
_AUDIT_PAYLOAD_CHUNK_SIZE = 50
_DATE_PATTERN = re.compile(r"(?:^|;)date=(\d{8}|\d{4}/\d{2}/\d{2})(?:;|$)")


@dataclass(frozen=True)
class EligibleBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    source: str
    raw_payload_id: int | None


def get_data(
    symbols: str | Sequence[str],
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    market: str | None = None,
) -> pd.DataFrame:
    return daily_bars_repository.get_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        source=source,
        market=market,
    )


def _audit_trading_date(expected_symbol_context: str) -> date | None:
    match = _DATE_PATTERN.search(expected_symbol_context or "")
    if match is None:
        return None
    value = match.group(1)
    try:
        format_string = "%Y%m%d" if "/" not in value else "%Y/%m/%d"
        return datetime.strptime(value, format_string).date()
    except ValueError:
        return None


def load_official_no_data_dates(*, start_date: date, end_date: date) -> set[date]:
    """Return dates where both official TW batch sources last reported no data."""
    fetch_timestamp_floor = datetime.combine(
        start_date,
        time.min,
        tzinfo=TW_TIMEZONE,
    ).astimezone(timezone.utc)
    latest_by_date_source: dict[tuple[date, str], tuple[int, str]] = {}
    try:
        rows = official_audits_repository.list_official_audit_metadata(
            market="TW",
            source_names=_BATCH_SOURCES,
            fetch_timestamp_floor=fetch_timestamp_floor,
        )
        for audit_id, source_name, fetch_status, expected_symbol_context in rows:
            trading_date = _audit_trading_date(expected_symbol_context)
            if trading_date is not None and start_date <= trading_date <= end_date:
                latest_by_date_source[trading_date, source_name] = (
                    audit_id,
                    fetch_status,
                )
    except Exception:
        logger.warning(
            "Failed to load official TW no-data audits start=%s end=%s; "
            "retaining all rows.",
            start_date,
            end_date,
            exc_info=True,
        )
        return set()

    try:
        successful_audit_ids = [
            audit_id
            for audit_id, fetch_status in latest_by_date_source.values()
            if fetch_status == "success"
        ]
        no_data_audit_ids: set[int] = set()
        for offset in range(
            0,
            len(successful_audit_ids),
            _AUDIT_PAYLOAD_CHUNK_SIZE,
        ):
            payloads = official_audits_repository.load_audit_payloads(
                successful_audit_ids[offset : offset + _AUDIT_PAYLOAD_CHUNK_SIZE]
            )
            no_data_audit_ids.update(
                audit_id
                for audit_id, payload in payloads.items()
                if official_daily.payload_declares_no_data(payload)
            )
        return {
            trading_date
            for trading_date in {key[0] for key in latest_by_date_source}
            if all(
                (audit := latest_by_date_source.get((trading_date, source)))
                is not None
                and audit[1] == "success"
                and audit[0] in no_data_audit_ids
                for source in _BATCH_SOURCES
            )
        }
    except Exception:
        logger.warning(
            "Failed to evaluate official TW no-data audits start=%s end=%s; "
            "retaining all rows.",
            start_date,
            end_date,
            exc_info=True,
        )
        return set()


def exclude_non_official_rows_on_official_no_data(
    frame: pd.DataFrame, official_no_data_dates: set[date]
) -> pd.DataFrame:
    if frame.empty or "source" not in frame.columns or not official_no_data_dates:
        return frame
    row_dates = pd.to_datetime(frame.index, errors="coerce").date
    excluded = (~frame["source"].isin(OFFICIAL_SOURCES)) & pd.Series(
        row_dates, index=frame.index
    ).isin(official_no_data_dates)
    return frame.loc[~excluded].copy()


def list_active_tw_research_symbols() -> list[str]:
    """Return the canonical current-active TWSE/TPEX research universe."""
    return sorted(
        {
            str(record["symbol"]).upper()
            for record in list_active_tw_company_profiles(limit=0)
            if str(record.get("market") or "").upper() == "TW"
            and str(record.get("exchange") or "").upper() in {"TWSE", "TPEX"}
            and str(record.get("symbol") or "").strip()
        }
    )


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        parsed = value.date()
        return parsed if type(parsed) is date else None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _as_positive_float(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(normalized) or normalized <= 0:
        return None
    return normalized


def _as_raw_payload_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(normalized) or not normalized.is_integer():
        return None
    return int(normalized)


def load_research_eligible_tw_bars(
    symbols: Iterable[str],
    *,
    start_date: date,
    end_date: date | None = None,
) -> dict[str, list[EligibleBar]]:
    requested = sorted(
        {str(item).strip().upper() for item in symbols if str(item).strip()}
    )
    if not requested:
        return {}
    frame = get_data(
        requested,
        start_date=start_date,
        end_date=end_date,
        market="TW",
    )
    if frame.empty:
        return {}
    normalized = frame.reset_index().set_index("date")
    normalized = exclude_non_official_rows_on_official_no_data(
        normalized,
        load_official_no_data_dates(
            start_date=start_date,
            end_date=end_date or datetime.now(TW_TIMEZONE).date(),
        ),
    )
    result: dict[str, list[EligibleBar]] = defaultdict(list)
    for row in normalized.reset_index().itertuples(index=False):
        open_, high, low, close = (
            _as_positive_float(value)
            for value in (row.open, row.high, row.low, row.close)
        )
        trading_date = _as_date(row.date)
        if (
            trading_date is None
            or open_ is None
            or high is None
            or low is None
            or close is None
        ):
            continue
        result[str(row.symbol).upper()].append(
            EligibleBar(
                date=trading_date,
                open=open_,
                high=high,
                low=low,
                close=close,
                source=str(row.source),
                raw_payload_id=_as_raw_payload_id(row.raw_payload_id),
            )
        )
    return dict(result)
