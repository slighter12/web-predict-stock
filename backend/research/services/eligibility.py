from __future__ import annotations

import logging
import re
from datetime import date, datetime

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
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(RawIngestAudit)
                .where(RawIngestAudit.market == "TW")
                .where(RawIngestAudit.source_name.in_(_BATCH_SOURCES))
                .order_by(
                    RawIngestAudit.fetch_timestamp.asc(), RawIngestAudit.id.asc()
                )
            ).scalars()

            latest_by_date_source: dict[tuple[date, str], object] = {}
            for row in rows:
                trading_date = _audit_trading_date(row.expected_symbol_context)
                if trading_date is not None and start_date <= trading_date <= end_date:
                    latest_by_date_source[trading_date, row.source_name] = row
    except Exception:
        logger.warning(
            "Failed to load official TW no-data audits start=%s end=%s; retaining all rows.",
            start_date,
            end_date,
        )
        return set()

    return {
        trading_date
        for trading_date in {key[0] for key in latest_by_date_source}
        if all(
            (row := latest_by_date_source.get((trading_date, source))) is not None
            and row.fetch_status == "success"
            and market_data_ingestion._payload_declares_no_data(row.payload_body)
            for source in _BATCH_SOURCES
        )
    }


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
