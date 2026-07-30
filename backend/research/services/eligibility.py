from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timezone

import pandas as pd
from sqlalchemy import select

from backend.database import RawIngestAudit, SessionLocal
from scripts import market_data_ingestion as market_data_ingestion

logger = logging.getLogger(__name__)

_BATCH_SOURCES = (
    market_data_ingestion.SOURCE_TWSE_MI_INDEX,
    market_data_ingestion.SOURCE_TPEX_AFTERTRADING_OTC,
)
_DATE_PATTERN = re.compile(r"(?:^|;)date=(\d{8}|\d{4}/\d{2}/\d{2})(?:;|$)")


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
        tzinfo=market_data_ingestion.TW_TIMEZONE,
    ).astimezone(timezone.utc)
    latest_by_date_source: dict[tuple[date, str], tuple[str, str | None]] = {}
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    RawIngestAudit.source_name,
                    RawIngestAudit.fetch_status,
                    RawIngestAudit.expected_symbol_context,
                    RawIngestAudit.payload_body,
                )
                .where(RawIngestAudit.market == "TW")
                .where(RawIngestAudit.source_name.in_(_BATCH_SOURCES))
                .where(RawIngestAudit.fetch_timestamp >= fetch_timestamp_floor)
                .order_by(
                    RawIngestAudit.fetch_timestamp.asc(), RawIngestAudit.id.asc()
                )
            )

            for row in rows:
                trading_date = _audit_trading_date(row.expected_symbol_context)
                if trading_date is not None and start_date <= trading_date <= end_date:
                    latest_by_date_source[trading_date, row.source_name] = (
                        row.fetch_status,
                        row.payload_body,
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
        return {
            trading_date
            for trading_date in {key[0] for key in latest_by_date_source}
            if all(
                (audit := latest_by_date_source.get((trading_date, source)))
                is not None
                and audit[0] == "success"
                and market_data_ingestion.payload_declares_no_data(audit[1])
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
    df: pd.DataFrame, official_no_data_dates: set[date]
) -> pd.DataFrame:
    if df.empty or "source" not in df.columns or not official_no_data_dates:
        return df
    row_dates = pd.to_datetime(df.index).date
    excluded = (~df["source"].isin(market_data_ingestion.OFFICIAL_SOURCES)) & pd.Series(
        row_dates, index=df.index
    ).isin(official_no_data_dates)
    return df.loc[~excluded].copy()
