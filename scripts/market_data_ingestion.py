import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from functools import partial
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import text

try:
    from backend.database import (
        DailyOHLCV,
        MinuteOHLCV,
        RawIngestAudit,
        engine,
    )
    from backend.market_data.services.company_crawlers import crawl_tw_company_profiles
    from backend.market_data.services.company_profiles import (
        list_active_tw_company_profiles,
    )
    from backend.market_data.services.tls_helpers import (
        request_with_tls_fallback,
    )
    from backend.platform.time import utc_now
except ImportError:
    print(
        "Error: Could not import from backend.database. Make sure the backend directory is in the Python path."
    )
    sys.exit(1)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

SOURCE_TWSE = "twse"
SOURCE_YFINANCE = "yfinance"
SOURCE_YFINANCE_MINUTE_1M = "yfinance_minute_1m"
SOURCE_TWSE_MI_INDEX = "twse_mi_index"
SOURCE_TPEX_AFTERTRADING_OTC = "tpex_aftertrading_otc"
MARKET_TW = "TW"
MARKET_US = "US"
TWSE_BATCH_SYMBOL = "TWSE_BATCH_DAILY"
TPEX_BATCH_SYMBOL = "TPEX_BATCH_DAILY"
TWSE_MI_INDEX_TYPE = "ALLBUT0999"
TPEX_AFTERTRADING_TYPE = "AL"
OFFICIAL_BATCH_TIMEOUT_SECONDS = int(os.getenv("OFFICIAL_BATCH_TIMEOUT_SECONDS", "60"))
YFINANCE_MINUTE_INTERVAL = "1m"
YFINANCE_MINUTE_SEGMENT_DAYS = 7
YFINANCE_MINUTE_WINDOW_DAYS = 30
YFINANCE_MINUTE_WINDOW_BUFFER_SECONDS = 1
TW_TIMEZONE = ZoneInfo("Asia/Taipei")
OFFICIAL_SOURCES = (
    SOURCE_TWSE,
    SOURCE_TWSE_MI_INDEX,
    SOURCE_TPEX_AFTERTRADING_OTC,
)


@dataclass
class QualityReport:
    input_rows: int
    duplicates_removed: int = 0
    null_rows_removed: int = 0
    invalid_rows_removed: int = 0
    gap_warnings: int = 0
    output_rows: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RawTraceMetadata:
    raw_payload_id: int | None = None
    archive_object_reference: str | None = None
    parser_version: str | None = None

    @classmethod
    def from_ingest(
        cls, raw_payload_id: int | None, parser_version: str
    ) -> "RawTraceMetadata":
        return cls(
            raw_payload_id=raw_payload_id,
            archive_object_reference=f"raw_ingest_audit:{raw_payload_id}"
            if raw_payload_id
            else None,
            parser_version=parser_version,
        )


TWSE_PARSER_VERSION = "twse_parser_v1"
YFINANCE_PARSER_VERSION = "yfinance_parser_v1"
YFINANCE_MINUTE_PARSER_VERSION = "yfinance_minute_1m_parser_v1"
TWSE_MI_INDEX_PARSER_VERSION = "twse_mi_index_v1"
TPEX_AFTERTRADING_OTC_PARSER_VERSION = "tpex_aftertrading_otc_v1"
FETCH_STATUS_SUCCESS = "success"
FETCH_STATUS_FAILED = "failed"


@dataclass
class BatchFetchResult:
    source_name: str
    dataframe: pd.DataFrame
    raw_row_count: int
    metadata: RawTraceMetadata | None = None
    error_message: str | None = None


def persist_raw_ingest_record(
    source_name: str,
    symbol: str,
    market: str,
    parser_version: str,
    fetch_status: str,
    expected_symbol_context: str,
    payload_body: str,
    fetch_timestamp: datetime | None = None,
) -> int:
    record = {
        "source_name": source_name,
        "symbol": symbol,
        "market": market,
        "fetch_timestamp": fetch_timestamp or utc_now(),
        "parser_version": parser_version,
        "fetch_status": fetch_status,
        "expected_symbol_context": expected_symbol_context,
        "payload_body": payload_body,
    }
    try:
        with engine.begin() as conn:
            insert_stmt = (
                RawIngestAudit.__table__.insert()
                .values(record)
                .returning(RawIngestAudit.id)
            )
            return conn.execute(insert_stmt).scalar_one()
    except Exception as exc:
        logger.exception(
            "Failed to persist raw ingest audit record source=%s symbol=%s",
            source_name,
            symbol,
        )
        raise RuntimeError("Failed to persist raw ingest audit record.") from exc


def _try_persist(
    persist_fn, *, fetch_status: str, payload_body: str, context_label: str
) -> int | None:
    try:
        return persist_fn(fetch_status=fetch_status, payload_body=payload_body)
    except RuntimeError:
        logger.warning("Failed to record audit for %s", context_label)
        return None


def to_yfinance_ticker(symbol: str, market: str) -> str:
    market_code = (market or "").upper()
    if market_code == MARKET_TW and "." not in symbol:
        return f"{symbol}.TW"
    return symbol


def _normalize_field_name(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _find_field_name(fields: list[str], aliases: tuple[str, ...]) -> str:
    normalized = {_normalize_field_name(field): field for field in fields}
    for alias in aliases:
        matched = normalized.get(_normalize_field_name(alias))
        if matched is not None:
            return matched
    raise ValueError(f"Required field aliases={aliases} were not found.")


def _sanitize_numeric_value(value) -> float:
    text = str(value).strip()
    if text in {"", "--", "---", "----"}:
        return 0.0
    sanitized = re.sub(r"<[^>]+>", "", text).replace(",", "").strip()
    numeric = pd.to_numeric(sanitized, errors="coerce")
    if pd.isna(numeric):
        return 0.0
    return float(numeric)


def _build_ohlcv_frame(
    *,
    rows: list[dict[str, object]],
    trading_date: date,
    source_name: str,
    market: str,
) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "market",
                "source",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

    df = pd.DataFrame(rows)
    df["date"] = trading_date
    df["market"] = market
    df["source"] = source_name
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].map(_sanitize_numeric_value)
    df["volume"] = df["volume"].astype(int)
    return df[
        ["date", "symbol", "market", "source", "open", "high", "low", "close", "volume"]
    ]


def _empty_batch_result(
    source_name: str, error_message: str | None = None
) -> BatchFetchResult:
    return BatchFetchResult(
        source_name=source_name,
        dataframe=pd.DataFrame(),
        raw_row_count=0,
        metadata=None,
        error_message=error_message,
    )


def validate_ohlcv_with_report(
    df: pd.DataFrame, label: str = ""
) -> tuple[pd.DataFrame, QualityReport]:
    report = QualityReport(input_rows=len(df))
    if df.empty:
        return df, report

    required_cols = ["date", "symbol", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.warning(
            "Missing columns in OHLCV data label=%s missing=%s", label, missing
        )
        return pd.DataFrame(), report

    cleaned = df.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"]).dt.date

    before_dedup = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=["date", "symbol"], keep="last")
    report.duplicates_removed = before_dedup - len(cleaned)

    null_rows = cleaned[required_cols].isnull().any(axis=1)
    report.null_rows_removed = int(null_rows.sum())
    if report.null_rows_removed:
        cleaned = cleaned[~null_rows]

    invalid_price = (cleaned[["open", "high", "low", "close"]] <= 0).any(axis=1)
    invalid_volume = cleaned["volume"] < 0
    invalid_rows = invalid_price | invalid_volume
    report.invalid_rows_removed = int(invalid_rows.sum())
    if report.invalid_rows_removed:
        cleaned = cleaned[~invalid_rows]

    if len(cleaned) > 1:
        sorted_dates = pd.to_datetime(cleaned["date"]).sort_values()
        gap_days = sorted_dates.diff().dt.days
        report.gap_warnings = int((gap_days > 7).sum())
        if report.gap_warnings:
            logger.warning(
                "Detected long gaps in OHLCV data label=%s gaps=%s",
                label,
                report.gap_warnings,
            )

    report.output_rows = len(cleaned)
    logger.info("Validated OHLCV label=%s report=%s", label, report.to_dict())
    return cleaned, report


def validate_ohlcv(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    cleaned, _ = validate_ohlcv_with_report(df, label=label)
    return cleaned


def validate_minute_ohlcv_with_report(
    df: pd.DataFrame, label: str = ""
) -> tuple[pd.DataFrame, QualityReport]:
    report = QualityReport(input_rows=len(df))
    if df.empty:
        return df, report

    required_cols = [
        "trading_date",
        "bar_ts",
        "symbol",
        "market",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.warning(
            "Missing columns in minute OHLCV data label=%s missing=%s", label, missing
        )
        return pd.DataFrame(), report

    cleaned = df.copy()
    cleaned["bar_ts"] = pd.to_datetime(cleaned["bar_ts"], utc=True, errors="coerce")
    cleaned["trading_date"] = pd.to_datetime(cleaned["trading_date"]).dt.date

    before_dedup = len(cleaned)
    cleaned = cleaned.drop_duplicates(
        subset=["market", "symbol", "bar_ts"], keep="last"
    )
    report.duplicates_removed = before_dedup - len(cleaned)

    null_rows = cleaned[required_cols].isnull().any(axis=1)
    report.null_rows_removed = int(null_rows.sum())
    if report.null_rows_removed:
        cleaned = cleaned[~null_rows]

    invalid_price = (cleaned[["open", "high", "low", "close"]] <= 0).any(axis=1)
    invalid_volume = cleaned["volume"] < 0
    invalid_rows = invalid_price | invalid_volume
    report.invalid_rows_removed = int(invalid_rows.sum())
    if report.invalid_rows_removed:
        cleaned = cleaned[~invalid_rows]

    report.output_rows = len(cleaned)
    logger.info("Validated minute OHLCV label=%s report=%s", label, report.to_dict())
    return cleaned, report


def _empty_minute_supplement_summary(
    *,
    status: str,
    window_start: date | None,
    window_end: date | None,
    skipped_reason: str | None = None,
) -> dict:
    return {
        "status": status,
        "window_start": window_start,
        "window_end": window_end,
        "segment_count": 0,
        "segments_succeeded": 0,
        "segments_failed": 0,
        "covered_trading_days": 0,
        "input_rows": 0,
        "upserted_rows": 0,
        "duplicates_removed": 0,
        "skipped_reason": skipped_reason,
    }


def _current_tw_now(reference_time: datetime | None = None) -> datetime:
    current = reference_time or utc_now()
    return current.astimezone(TW_TIMEZONE)


def _resolve_minute_window(
    reference_time: datetime | None = None,
) -> tuple[datetime, datetime]:
    window_end = _current_tw_now(reference_time)
    window_start = window_end - timedelta(days=YFINANCE_MINUTE_WINDOW_DAYS)
    window_start += timedelta(seconds=YFINANCE_MINUTE_WINDOW_BUFFER_SECONDS)
    return window_start, window_end


def _parse_ingestion_date_override(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        return None


def _list_symbol_daily_trading_days(
    *,
    symbol: str,
    market: str,
    start_date: date,
    end_date: date,
) -> list[date]:
    query = text(
        f"""
        SELECT DISTINCT date
        FROM {DailyOHLCV.__tablename__}
        WHERE symbol = :symbol
          AND market = :market
          AND date >= :start_date
          AND date <= :end_date
        ORDER BY date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "symbol": symbol,
                "market": market,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalars()
        return [item for item in rows if item is not None]


def _list_symbol_minute_trading_days(
    *,
    symbol: str,
    market: str,
    start_date: date,
    end_date: date,
) -> list[date]:
    query = text(
        f"""
        SELECT DISTINCT trading_date
        FROM {MinuteOHLCV.__tablename__}
        WHERE symbol = :symbol
          AND market = :market
          AND trading_date >= :start_date
          AND trading_date <= :end_date
        ORDER BY trading_date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "symbol": symbol,
                "market": market,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalars()
        return [item for item in rows if item is not None]


def _build_minute_fetch_segments(
    *,
    missing_days: list[date],
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    if not missing_days:
        return []

    segments: list[tuple[datetime, datetime]] = []
    sorted_days = sorted(missing_days)
    index = 0
    while index < len(sorted_days):
        segment_start_day = sorted_days[index]
        segment_end_day = min(
            segment_start_day + timedelta(days=YFINANCE_MINUTE_SEGMENT_DAYS - 1),
            window_end.date(),
        )
        segment_start = max(
            datetime.combine(segment_start_day, datetime.min.time(), tzinfo=TW_TIMEZONE),
            window_start,
        )
        segment_end = min(
            datetime.combine(
                segment_end_day + timedelta(days=1),
                datetime.min.time(),
                tzinfo=TW_TIMEZONE,
            ),
            window_end,
        )
        if segment_start < segment_end:
            segments.append((segment_start, segment_end))
        while index < len(sorted_days) and sorted_days[index] <= segment_end_day:
            index += 1
    return segments


def _attach_stage_metadata(summary: dict, metadata: RawTraceMetadata | None) -> dict:
    enriched = dict(summary)
    enriched["raw_payload_id"] = metadata.raw_payload_id if metadata else None
    enriched["archive_object_reference"] = (
        metadata.archive_object_reference if metadata else None
    )
    enriched["parser_version"] = metadata.parser_version if metadata else None
    return enriched


def parse_twse_payload_body(
    payload_body: str,
    symbol: str,
    raw_payload_id: int | None = None,
) -> tuple[pd.DataFrame, RawTraceMetadata]:
    data = json.loads(payload_body)
    if data.get("stat") != "OK":
        raise ValueError(f"TWSE payload is not replayable for symbol '{symbol}'.")

    df = pd.DataFrame(data["data"], columns=data["fields"])
    column_mapping = {
        "日期": "date",
        "成交股數": "volume",
        "成交金額": "trade_value",
        "開盤價": "open",
        "最高價": "high",
        "最低價": "low",
        "收盤價": "close",
        "漲跌價差": "price_change",
        "成交筆數": "trade_count",
    }
    df.rename(columns=column_mapping, inplace=True)
    df["symbol"] = symbol
    df["source"] = SOURCE_TWSE
    df["market"] = MARKET_TW
    df["date"] = df["date"].apply(
        lambda d: datetime.strptime(
            f"{int(d.split('/')[0]) + 1911}/{d.split('/')[1]}/{d.split('/')[2]}",
            "%Y/%m/%d",
        ).date()
    )

    for col in ["volume", "open", "high", "low", "close"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", ""),
            errors="coerce",
        ).fillna(0)

    df["volume"] = df["volume"].astype(int)
    df = df[
        [
            "date",
            "symbol",
            "market",
            "source",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    cleaned, _ = validate_ohlcv_with_report(df, label=f"{symbol}:{SOURCE_TWSE}:replay")
    return cleaned, RawTraceMetadata.from_ingest(raw_payload_id, TWSE_PARSER_VERSION)


def parse_yfinance_payload_body(
    payload_body: str,
    symbol: str,
    market: str,
    raw_payload_id: int | None = None,
) -> tuple[pd.DataFrame, RawTraceMetadata]:
    hist = pd.read_json(StringIO(payload_body), orient="table")
    hist.rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        },
        inplace=True,
    )
    for col in ["open", "high", "low", "close", "volume"]:
        hist[col] = pd.to_numeric(hist[col], errors="coerce")

    hist["date"] = pd.to_datetime(hist["date"]).dt.date
    hist["symbol"] = symbol
    hist["source"] = SOURCE_YFINANCE
    hist["market"] = market
    hist["volume"] = hist["volume"].fillna(0).astype(int)
    hist = hist[
        ["date", "symbol", "market", "source", "open", "high", "low", "close", "volume"]
    ]
    cleaned, _ = validate_ohlcv_with_report(
        hist, label=f"{symbol}:{SOURCE_YFINANCE}:replay"
    )
    return cleaned, RawTraceMetadata.from_ingest(
        raw_payload_id, YFINANCE_PARSER_VERSION
    )


def parse_yfinance_minute_payload_body(
    payload_body: str,
    *,
    symbol: str,
    market: str,
    raw_payload_id: int | None = None,
) -> tuple[pd.DataFrame, RawTraceMetadata]:
    payload = json.loads(payload_body)
    hist = pd.DataFrame(payload.get("data", []))
    hist.rename(
        columns={
            "Date": "bar_ts",
            "Datetime": "bar_ts",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        },
        inplace=True,
    )

    bar_ts = pd.to_datetime(hist["bar_ts"], errors="coerce")
    if getattr(bar_ts.dt, "tz", None) is None:
        local_bar_ts = bar_ts.dt.tz_localize(TW_TIMEZONE)
    else:
        local_bar_ts = bar_ts.dt.tz_convert(TW_TIMEZONE)

    hist["trading_date"] = local_bar_ts.dt.date
    hist["bar_ts"] = local_bar_ts.dt.tz_convert(timezone.utc)
    hist["symbol"] = symbol
    hist["market"] = market
    hist["source"] = SOURCE_YFINANCE_MINUTE_1M

    for col in ["open", "high", "low", "close", "volume"]:
        hist[col] = pd.to_numeric(hist[col], errors="coerce")
    hist["volume"] = hist["volume"].fillna(0).astype(int)
    hist = hist[
        [
            "trading_date",
            "bar_ts",
            "symbol",
            "market",
            "source",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]
    cleaned, _ = validate_minute_ohlcv_with_report(
        hist, label=f"{symbol}:{SOURCE_YFINANCE_MINUTE_1M}:replay"
    )
    return cleaned, RawTraceMetadata.from_ingest(
        raw_payload_id, YFINANCE_MINUTE_PARSER_VERSION
    )


def replay_raw_ingest_record(raw_record) -> tuple[pd.DataFrame, RawTraceMetadata]:
    if not getattr(raw_record, "payload_body", None):
        raise ValueError(
            f"Raw payload '{raw_record.id}' does not contain replayable content."
        )

    if raw_record.source_name == SOURCE_TWSE:
        return parse_twse_payload_body(
            payload_body=raw_record.payload_body,
            symbol=raw_record.symbol,
            raw_payload_id=raw_record.id,
        )
    if raw_record.source_name == SOURCE_YFINANCE:
        return parse_yfinance_payload_body(
            payload_body=raw_record.payload_body,
            symbol=raw_record.symbol,
            market=raw_record.market,
            raw_payload_id=raw_record.id,
        )

    raise ValueError(
        f"Unsupported source '{raw_record.source_name}' for raw payload replay."
    )


def resolve_tw_active_universe() -> dict[str, set[str]]:
    universe = {"TWSE": set(), "TPEX": set()}
    for record in list_active_tw_company_profiles(limit=0):
        exchange = str(record.get("exchange") or "").upper()
        symbol = str(record.get("symbol") or "").upper()
        if exchange in universe and symbol:
            universe[exchange].add(symbol)
    return universe


def parse_twse_mi_index_payload_body(
    payload_body: str,
    *,
    trading_date: date,
    raw_payload_id: int | None = None,
) -> tuple[pd.DataFrame, RawTraceMetadata]:
    payload = json.loads(payload_body)
    if payload.get("stat") != "OK":
        raise ValueError("TWSE MI_INDEX payload is not replayable.")

    tables = payload.get("tables") or []
    selected_table = None
    for table in tables:
        fields = [str(field).strip() for field in table.get("fields", [])]
        normalized = {_normalize_field_name(field) for field in fields}
        if "證券代號" in fields or "security code" in normalized:
            selected_table = table
            break
    if selected_table is None:
        raise ValueError("TWSE MI_INDEX stock table was not found.")

    fields = [str(field).strip() for field in selected_table.get("fields", [])]
    field_map = {
        "symbol": _find_field_name(fields, ("證券代號", "security code", "code")),
        "open": _find_field_name(fields, ("開盤價", "open")),
        "high": _find_field_name(fields, ("最高價", "high")),
        "low": _find_field_name(fields, ("最低價", "low")),
        "close": _find_field_name(fields, ("收盤價", "close")),
        "volume": _find_field_name(
            fields,
            ("成交股數", "trade volume (shares)", "trade vol. (shares)"),
        ),
    }

    rows = []
    for item in selected_table.get("data", []):
        if not isinstance(item, list):
            continue
        row = dict(zip(fields, item))
        rows.append(
            {
                "symbol": str(row[field_map["symbol"]]).strip().upper(),
                "open": row[field_map["open"]],
                "high": row[field_map["high"]],
                "low": row[field_map["low"]],
                "close": row[field_map["close"]],
                "volume": row[field_map["volume"]],
            }
        )

    return _build_ohlcv_frame(
        rows=rows,
        trading_date=trading_date,
        source_name=SOURCE_TWSE_MI_INDEX,
        market=MARKET_TW,
    ), RawTraceMetadata.from_ingest(raw_payload_id, TWSE_MI_INDEX_PARSER_VERSION)


def parse_tpex_aftertrading_payload_body(
    payload_body: str,
    *,
    trading_date: date,
    raw_payload_id: int | None = None,
) -> tuple[pd.DataFrame, RawTraceMetadata]:
    payload = json.loads(payload_body)
    if str(payload.get("stat")).lower() != "ok":
        raise ValueError("TPEX afterTrading payload is not replayable.")

    tables = payload.get("tables") or []
    if not tables:
        raise ValueError("TPEX afterTrading payload does not contain tables.")
    selected_table = tables[0]
    fields = [str(field).strip() for field in selected_table.get("fields", [])]
    field_map = {
        "symbol": _find_field_name(fields, ("代號", "code", "security code")),
        "open": _find_field_name(fields, ("開盤", "open", "open ")),
        "high": _find_field_name(fields, ("最高", "high", "high ")),
        "low": _find_field_name(fields, ("最低", "low")),
        "close": _find_field_name(fields, ("收盤", "close", "close ")),
        "volume": _find_field_name(
            fields,
            ("成交股數", "trade vol. (shares)", "trade volume (shares)"),
        ),
    }

    rows = []
    for item in selected_table.get("data", []):
        if not isinstance(item, list):
            continue
        row = dict(zip(fields, item))
        rows.append(
            {
                "symbol": str(row[field_map["symbol"]]).strip().upper(),
                "open": row[field_map["open"]],
                "high": row[field_map["high"]],
                "low": row[field_map["low"]],
                "close": row[field_map["close"]],
                "volume": row[field_map["volume"]],
            }
        )

    return _build_ohlcv_frame(
        rows=rows,
        trading_date=trading_date,
        source_name=SOURCE_TPEX_AFTERTRADING_OTC,
        market=MARKET_TW,
    ), RawTraceMetadata.from_ingest(
        raw_payload_id, TPEX_AFTERTRADING_OTC_PARSER_VERSION
    )


def _filter_batch_frame_to_universe(
    df: pd.DataFrame,
    *,
    allowed_symbols: set[str],
) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["symbol"].isin(allowed_symbols)].copy()


def _attach_frame_metadata(
    df: pd.DataFrame,
    metadata: RawTraceMetadata | None,
) -> pd.DataFrame:
    enriched = df.copy()
    enriched["raw_payload_id"] = metadata.raw_payload_id if metadata else None
    enriched["archive_object_reference"] = (
        metadata.archive_object_reference if metadata else None
    )
    enriched["parser_version"] = metadata.parser_version if metadata else None
    return enriched


def scrape_twse_data(
    symbol: str, date_str: str | None = None
) -> tuple[pd.DataFrame, RawTraceMetadata | None]:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    fetch_timestamp = utc_now()
    expected_context = f"symbol={symbol};market={MARKET_TW}"
    payload_body = ""

    _persist = partial(
        persist_raw_ingest_record,
        source_name=SOURCE_TWSE,
        symbol=symbol,
        market=MARKET_TW,
        parser_version=TWSE_PARSER_VERSION,
        expected_symbol_context=expected_context,
        fetch_timestamp=fetch_timestamp,
    )

    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={symbol}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    raw_payload_id = None
    try:
        response = _request_twse_daily_report(
            url=url,
            headers=headers,
            timeout_seconds=OFFICIAL_BATCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException:
        logger.exception("TWSE request failed symbol=%s date=%s", symbol, date_str)
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"TWSE fetch failure {symbol}",
        )
        return pd.DataFrame(), None

    raw_payload_id = _persist(
        fetch_status=FETCH_STATUS_SUCCESS,
        payload_body=payload_body,
    )

    try:
        data = response.json()
        if data.get("stat") != "OK":
            logger.warning(
                "TWSE returned non-OK status symbol=%s date=%s detail=%s",
                symbol,
                date_str,
                data,
            )
            _try_persist(
                _persist,
                fetch_status=FETCH_STATUS_FAILED,
                payload_body=payload_body,
                context_label=f"TWSE non-OK {symbol}",
            )
            return pd.DataFrame(), None

        cleaned, metadata = parse_twse_payload_body(
            payload_body=payload_body,
            symbol=symbol,
            raw_payload_id=raw_payload_id,
        )

        logger.info(
            "Scraped TWSE rows=%s symbol=%s month=%s",
            len(cleaned),
            symbol,
            date_str[:6],
        )
        return cleaned, metadata
    except Exception:
        logger.exception(
            "TWSE payload parsing failed symbol=%s date=%s", symbol, date_str
        )
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"TWSE parse failure {symbol}",
        )
        return pd.DataFrame(), None


def _request_twse_daily_report(
    *, url: str, headers: dict[str, str], timeout_seconds: int
) -> requests.Response:
    return request_with_tls_fallback(
        method="GET",
        url=url,
        headers=headers,
        timeout_seconds=timeout_seconds,
        logger=logger,
        context_label="TWSE daily report fetch",
    )


def _request_tpex_daily_report(
    *,
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    data: dict[str, str],
) -> requests.Response:
    return request_with_tls_fallback(
        method="POST",
        url=url,
        headers=headers,
        data=data,
        timeout_seconds=timeout_seconds,
        logger=logger,
        context_label="TPEX daily report fetch",
    )


def fetch_twse_market_batch(trading_date: date) -> BatchFetchResult:
    trading_date_str = trading_date.strftime("%Y%m%d")
    fetch_timestamp = utc_now()
    payload_body = ""
    expected_context = f"market={MARKET_TW};exchange=TWSE;date={trading_date_str};type={TWSE_MI_INDEX_TYPE}"
    _persist = partial(
        persist_raw_ingest_record,
        source_name=SOURCE_TWSE_MI_INDEX,
        symbol=TWSE_BATCH_SYMBOL,
        market=MARKET_TW,
        parser_version=TWSE_MI_INDEX_PARSER_VERSION,
        expected_symbol_context=expected_context,
        fetch_timestamp=fetch_timestamp,
    )
    url = (
        "https://www.twse.com.tw/exchangeReport/MI_INDEX"
        f"?response=json&date={trading_date_str}&type={TWSE_MI_INDEX_TYPE}"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        response = _request_twse_daily_report(
            url=url, headers=headers, timeout_seconds=30
        )
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException as exc:
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=SOURCE_TWSE_MI_INDEX,
        )
        return _empty_batch_result(
            SOURCE_TWSE_MI_INDEX,
            error_message=f"TWSE batch fetch failed: {exc}",
        )

    raw_payload_id = _persist(
        fetch_status=FETCH_STATUS_SUCCESS,
        payload_body=payload_body,
    )

    try:
        dataframe, metadata = parse_twse_mi_index_payload_body(
            payload_body,
            trading_date=trading_date,
            raw_payload_id=raw_payload_id,
        )
    except Exception as exc:
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"{SOURCE_TWSE_MI_INDEX} parse failure",
        )
        return _empty_batch_result(
            SOURCE_TWSE_MI_INDEX,
            error_message=f"TWSE batch parse failed: {exc}",
        )

    return BatchFetchResult(
        source_name=SOURCE_TWSE_MI_INDEX,
        dataframe=dataframe,
        raw_row_count=len(dataframe),
        metadata=metadata,
    )


def fetch_tpex_market_batch(trading_date: date) -> BatchFetchResult:
    trading_date_str = trading_date.strftime("%Y/%m/%d")
    fetch_timestamp = utc_now()
    payload_body = ""
    expected_context = f"market={MARKET_TW};exchange=TPEX;date={trading_date_str};type={TPEX_AFTERTRADING_TYPE}"
    _persist = partial(
        persist_raw_ingest_record,
        source_name=SOURCE_TPEX_AFTERTRADING_OTC,
        symbol=TPEX_BATCH_SYMBOL,
        market=MARKET_TW,
        parser_version=TPEX_AFTERTRADING_OTC_PARSER_VERSION,
        expected_symbol_context=expected_context,
        fetch_timestamp=fetch_timestamp,
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    payload = {
        "date": trading_date_str,
        "type": TPEX_AFTERTRADING_TYPE,
        "response": "json",
    }

    try:
        response = _request_tpex_daily_report(
            url="https://www.tpex.org.tw/www/en-us/afterTrading/otc",
            headers=headers,
            timeout_seconds=OFFICIAL_BATCH_TIMEOUT_SECONDS,
            data=payload,
        )
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException as exc:
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=SOURCE_TPEX_AFTERTRADING_OTC,
        )
        return _empty_batch_result(
            SOURCE_TPEX_AFTERTRADING_OTC,
            error_message=f"TPEX batch fetch failed: {exc}",
        )

    raw_payload_id = _persist(
        fetch_status=FETCH_STATUS_SUCCESS,
        payload_body=payload_body,
    )

    try:
        dataframe, metadata = parse_tpex_aftertrading_payload_body(
            payload_body,
            trading_date=trading_date,
            raw_payload_id=raw_payload_id,
        )
    except Exception as exc:
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"{SOURCE_TPEX_AFTERTRADING_OTC} parse failure",
        )
        return _empty_batch_result(
            SOURCE_TPEX_AFTERTRADING_OTC,
            error_message=f"TPEX batch parse failed: {exc}",
        )

    return BatchFetchResult(
        source_name=SOURCE_TPEX_AFTERTRADING_OTC,
        dataframe=dataframe,
        raw_row_count=len(dataframe),
        metadata=metadata,
    )


def load_to_db(df: pd.DataFrame, metadata: RawTraceMetadata | None = None) -> dict:
    validated_df, quality = validate_ohlcv_with_report(df, label="load_to_db")
    raw_payload_id = metadata.raw_payload_id if metadata else None
    archive_object_reference = metadata.archive_object_reference if metadata else None
    parser_version = metadata.parser_version if metadata else None
    summary = {
        "input_rows": quality.input_rows,
        "validated_rows": quality.output_rows,
        "dropped_rows": quality.input_rows - quality.output_rows,
        "duplicates_removed": quality.duplicates_removed,
        "null_rows_removed": quality.null_rows_removed,
        "invalid_rows_removed": quality.invalid_rows_removed,
        "gap_warnings": quality.gap_warnings,
        "upserted_rows": 0,
        "official_overrides": 0,
    }
    if validated_df.empty:
        logger.info(
            "Skipping DB load because validated DataFrame is empty summary=%s", summary
        )
        return summary

    temp_table_name = "daily_ohlcv_temp"
    if not OFFICIAL_SOURCES:
        raise ValueError("OFFICIAL_SOURCES must not be empty.")
    official_source_params = {
        f"official_source_{index}": source
        for index, source in enumerate(OFFICIAL_SOURCES, start=1)
    }
    official_source_placeholders = ",\n                                ".join(
        f":official_source_{index}" for index in range(1, len(OFFICIAL_SOURCES) + 1)
    )
    try:
        validated_df = validated_df.copy()
        if "raw_payload_id" in validated_df.columns:
            validated_df["raw_payload_id"] = validated_df["raw_payload_id"].where(
                validated_df["raw_payload_id"].notna(), raw_payload_id
            )
        else:
            validated_df["raw_payload_id"] = raw_payload_id
        if "archive_object_reference" in validated_df.columns:
            validated_df["archive_object_reference"] = validated_df[
                "archive_object_reference"
            ].where(
                validated_df["archive_object_reference"].notna(),
                archive_object_reference,
            )
        else:
            validated_df["archive_object_reference"] = archive_object_reference
        if "parser_version" in validated_df.columns:
            validated_df["parser_version"] = validated_df["parser_version"].where(
                validated_df["parser_version"].notna(), parser_version
            )
        else:
            validated_df["parser_version"] = parser_version
        with engine.connect() as conn:
            with conn.begin():
                validated_df.to_sql(
                    temp_table_name, conn, if_exists="replace", index=False
                )

                override_count = conn.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM {DailyOHLCV.__tablename__} existing
                        INNER JOIN {temp_table_name} incoming
                            ON existing.date = incoming.date
                           AND existing.symbol = incoming.symbol
                        WHERE incoming.source IN (
                                {official_source_placeholders}
                        )
                          AND (
                            existing.source IS NULL
                            OR existing.source NOT IN (
                                {official_source_placeholders}
                            )
                          )
                        """
                    ),
                    official_source_params,
                ).scalar_one()

                result = conn.execute(
                    text(
                        f"""
                        INSERT INTO {DailyOHLCV.__tablename__} (
                            date, symbol, market, source, open, high, low, close, volume,
                            raw_payload_id, archive_object_reference, parser_version
                        )
                        SELECT date, symbol, market, source, open, high, low, close, volume,
                               raw_payload_id, archive_object_reference, parser_version
                        FROM {temp_table_name}
                        ON CONFLICT (date, symbol) DO UPDATE SET
                            market = EXCLUDED.market,
                            source = EXCLUDED.source,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            raw_payload_id = EXCLUDED.raw_payload_id,
                            archive_object_reference = EXCLUDED.archive_object_reference,
                            parser_version = EXCLUDED.parser_version
                        WHERE EXCLUDED.source IN (
                                {official_source_placeholders}
                            )
                           OR {DailyOHLCV.__tablename__}.source IS NULL
                           OR {DailyOHLCV.__tablename__}.source NOT IN (
                                {official_source_placeholders}
                            )
                        """
                    ),
                    official_source_params,
                )
        summary["official_overrides"] = int(override_count)
        summary["upserted_rows"] = (
            result.rowcount
            if result.rowcount and result.rowcount > 0
            else len(validated_df)
        )
        logger.info("Loaded OHLCV rows summary=%s", summary)
        return summary
    except Exception:
        logger.exception("Failed to load OHLCV rows summary=%s", summary)
        raise


def load_minute_to_db(
    df: pd.DataFrame, metadata: RawTraceMetadata | None = None
) -> dict:
    validated_df, quality = validate_minute_ohlcv_with_report(
        df, label="load_minute_to_db"
    )
    raw_payload_id = metadata.raw_payload_id if metadata else None
    parser_version = metadata.parser_version if metadata else None
    summary = {
        "input_rows": quality.input_rows,
        "validated_rows": quality.output_rows,
        "duplicates_removed": quality.duplicates_removed,
        "upserted_rows": 0,
    }
    if validated_df.empty:
        logger.info(
            "Skipping minute DB load because validated DataFrame is empty summary=%s",
            summary,
        )
        return summary

    temp_table_name = "minute_ohlcv_temp"
    try:
        validated_df = validated_df.copy()
        if "raw_payload_id" in validated_df.columns:
            validated_df["raw_payload_id"] = validated_df["raw_payload_id"].where(
                validated_df["raw_payload_id"].notna(), raw_payload_id
            )
        else:
            validated_df["raw_payload_id"] = raw_payload_id
        if "parser_version" in validated_df.columns:
            validated_df["parser_version"] = validated_df["parser_version"].where(
                validated_df["parser_version"].notna(), parser_version
            )
        else:
            validated_df["parser_version"] = parser_version

        with engine.connect() as conn:
            with conn.begin():
                validated_df.to_sql(
                    temp_table_name, conn, if_exists="replace", index=False
                )
                result = conn.execute(
                    text(
                        f"""
                        INSERT INTO {MinuteOHLCV.__tablename__} (
                            market, symbol, bar_ts, trading_date, source,
                            open, high, low, close, volume,
                            raw_payload_id, parser_version
                        )
                        SELECT market, symbol, bar_ts, trading_date, source,
                               open, high, low, close, volume,
                               raw_payload_id, parser_version
                        FROM {temp_table_name}
                        ON CONFLICT (market, symbol, bar_ts) DO UPDATE SET
                            trading_date = EXCLUDED.trading_date,
                            source = EXCLUDED.source,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            raw_payload_id = EXCLUDED.raw_payload_id,
                            parser_version = EXCLUDED.parser_version
                        """
                    )
                )
        summary["upserted_rows"] = (
            result.rowcount
            if result.rowcount and result.rowcount > 0
            else len(validated_df)
        )
        logger.info("Loaded minute OHLCV rows summary=%s", summary)
        return summary
    except Exception:
        logger.exception("Failed to load minute OHLCV rows summary=%s", summary)
        raise


def scrape_daily_twse(
    symbol: str, date_str: str | None = None
) -> tuple[pd.DataFrame, RawTraceMetadata | None]:
    month_df, metadata = scrape_twse_data(symbol=symbol, date_str=date_str)
    if month_df.empty:
        return month_df, metadata

    latest_date = max(month_df["date"])
    latest = month_df[month_df["date"] == latest_date].copy()
    logger.info("Selected latest TWSE daily row symbol=%s date=%s", symbol, latest_date)
    return latest, metadata


def backfill_history(
    symbol: str, years: int = 5, market: str = MARKET_TW
) -> tuple[pd.DataFrame, RawTraceMetadata | None]:
    if years < 1:
        raise ValueError("years must be >= 1")

    ticker_symbol = to_yfinance_ticker(symbol, market)
    fetch_timestamp = utc_now()
    start_date = fetch_timestamp - timedelta(days=365 * years)
    expected_context = f"symbol={symbol};market={market};years={years}"
    payload_body = ""

    _persist = partial(
        persist_raw_ingest_record,
        source_name=SOURCE_YFINANCE,
        symbol=symbol,
        market=market,
        parser_version=YFINANCE_PARSER_VERSION,
        expected_symbol_context=expected_context,
        fetch_timestamp=fetch_timestamp,
    )

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start_date, auto_adjust=False, actions=False)
    except Exception:
        logger.exception(
            "Failed to fetch yfinance data symbol=%s market=%s", symbol, market
        )
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"yfinance fetch failure {symbol}",
        )
        return pd.DataFrame(), None

    if hist.empty:
        logger.warning("No yfinance data returned symbol=%s market=%s", symbol, market)
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_SUCCESS,
            payload_body=payload_body,
            context_label=f"yfinance empty fetch {symbol}",
        )
        return pd.DataFrame(), None

    hist = hist.reset_index()
    raw_payload_body = hist.to_json(orient="table", date_format="iso")

    raw_payload_id = _persist(
        fetch_status=FETCH_STATUS_SUCCESS,
        payload_body=raw_payload_body,
    )

    cleaned, metadata = parse_yfinance_payload_body(
        payload_body=raw_payload_body,
        symbol=symbol,
        market=market,
        raw_payload_id=raw_payload_id,
    )
    logger.info(
        "Fetched yfinance history rows=%s symbol=%s market=%s",
        len(cleaned),
        symbol,
        market,
    )
    return cleaned, metadata


def fetch_yfinance_minute_segment(
    *,
    ticker,
    symbol: str,
    market: str,
    start_dt: datetime,
    end_dt: datetime,
) -> tuple[pd.DataFrame, RawTraceMetadata | None]:
    fetch_timestamp = utc_now()
    expected_context = (
        f"symbol={symbol};market={market};interval={YFINANCE_MINUTE_INTERVAL};"
        f"start={start_dt.astimezone(timezone.utc).isoformat()};"
        f"end={end_dt.astimezone(timezone.utc).isoformat()}"
    )
    payload_body = ""

    _persist = partial(
        persist_raw_ingest_record,
        source_name=SOURCE_YFINANCE_MINUTE_1M,
        symbol=symbol,
        market=market,
        parser_version=YFINANCE_MINUTE_PARSER_VERSION,
        expected_symbol_context=expected_context,
        fetch_timestamp=fetch_timestamp,
    )

    try:
        hist = ticker.history(
            start=start_dt.astimezone(timezone.utc),
            end=end_dt.astimezone(timezone.utc),
            interval=YFINANCE_MINUTE_INTERVAL,
            auto_adjust=False,
            actions=False,
        )
    except Exception:
        logger.exception(
            "Failed to fetch yfinance minute data symbol=%s market=%s start=%s end=%s",
            symbol,
            market,
            start_dt,
            end_dt,
        )
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"yfinance minute fetch failure {symbol}",
        )
        return pd.DataFrame(), None

    if hist.empty:
        logger.warning(
            "No yfinance minute data returned symbol=%s market=%s start=%s end=%s",
            symbol,
            market,
            start_dt,
            end_dt,
        )
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_SUCCESS,
            payload_body=payload_body,
            context_label=f"yfinance minute empty fetch {symbol}",
        )
        return pd.DataFrame(), None

    hist = hist.reset_index()
    payload_body = hist.to_json(orient="table", date_format="iso")
    raw_payload_id = _persist(
        fetch_status=FETCH_STATUS_SUCCESS,
        payload_body=payload_body,
    )

    try:
        cleaned, metadata = parse_yfinance_minute_payload_body(
            payload_body=payload_body,
            symbol=symbol,
            market=market,
            raw_payload_id=raw_payload_id,
        )
    except Exception:
        logger.exception(
            "Failed to parse yfinance minute data symbol=%s market=%s start=%s end=%s",
            symbol,
            market,
            start_dt,
            end_dt,
        )
        _try_persist(
            _persist,
            fetch_status=FETCH_STATUS_FAILED,
            payload_body=payload_body,
            context_label=f"yfinance minute parse failure {symbol}",
        )
        return pd.DataFrame(), None

    logger.info(
        "Fetched yfinance minute rows=%s symbol=%s market=%s start=%s end=%s",
        len(cleaned),
        symbol,
        market,
        start_dt,
        end_dt,
    )
    return cleaned, metadata


def supplement_yahoo_minute_history(
    *,
    symbol: str,
    market: str,
    date_str: str | None = None,
    reference_time: datetime | None = None,
) -> dict:
    market_code = (market or "").upper()
    window_start, window_end = _resolve_minute_window(reference_time)
    window_start_date = window_start.date()
    window_end_date = window_end.date()

    if market_code != MARKET_TW:
        return _empty_minute_supplement_summary(
            status="skipped",
            window_start=window_start_date,
            window_end=window_end_date,
            skipped_reason="market_not_supported",
        )

    override_date = _parse_ingestion_date_override(date_str)
    if date_str and override_date != window_end_date:
        return _empty_minute_supplement_summary(
            status="skipped",
            window_start=window_start_date,
            window_end=window_end_date,
            skipped_reason="historical_date_override_not_supported",
        )

    trading_days = _list_symbol_daily_trading_days(
        symbol=symbol,
        market=market_code,
        start_date=window_start_date,
        end_date=window_end_date,
    )
    if not trading_days:
        return _empty_minute_supplement_summary(
            status="skipped",
            window_start=window_start_date,
            window_end=window_end_date,
            skipped_reason="no_recent_trading_days",
        )

    covered_days = set(
        _list_symbol_minute_trading_days(
            symbol=symbol,
            market=market_code,
            start_date=window_start_date,
            end_date=window_end_date,
        )
    )
    missing_days = [day for day in trading_days if day not in covered_days]

    summary = _empty_minute_supplement_summary(
        status="succeeded",
        window_start=window_start_date,
        window_end=window_end_date,
    )
    summary["covered_trading_days"] = len(covered_days)
    if not missing_days:
        return summary

    segments = _build_minute_fetch_segments(
        missing_days=missing_days,
        window_start=window_start,
        window_end=window_end,
    )
    summary["segment_count"] = len(segments)
    ticker = yf.Ticker(to_yfinance_ticker(symbol, market_code))

    for segment_start, segment_end in segments:
        segment_df, metadata = fetch_yfinance_minute_segment(
            ticker=ticker,
            symbol=symbol,
            market=market_code,
            start_dt=segment_start,
            end_dt=segment_end,
        )
        if segment_df.empty or metadata is None:
            summary["segments_failed"] += 1
            continue

        load_summary = load_minute_to_db(segment_df, metadata=metadata)
        summary["segments_succeeded"] += 1
        summary["input_rows"] += int(load_summary["input_rows"])
        summary["upserted_rows"] += int(load_summary["upserted_rows"])
        summary["duplicates_removed"] += int(load_summary["duplicates_removed"])

    covered_days = set(
        _list_symbol_minute_trading_days(
            symbol=symbol,
            market=market_code,
            start_date=window_start_date,
            end_date=window_end_date,
        )
    )
    summary["covered_trading_days"] = len(covered_days)
    if summary["segments_failed"] and summary["segments_succeeded"]:
        summary["status"] = "partial_failure"
    elif summary["segments_failed"] and not summary["segments_succeeded"]:
        summary["status"] = "failed"

    return summary


def ingest_tw_market_batch(
    *,
    trading_date: date,
    refresh_universe: bool = False,
) -> dict:
    universe_refresh_summary = None
    if refresh_universe:
        universe_refresh_summary = crawl_tw_company_profiles()

    universe_by_exchange = resolve_tw_active_universe()
    universe_count = sum(len(symbols) for symbols in universe_by_exchange.values())
    if universe_count == 0:
        raise ValueError("Active TW company universe is empty.")

    twse_result = fetch_twse_market_batch(trading_date)
    tpex_result = fetch_tpex_market_batch(trading_date)

    filtered_frames = []
    errors = []
    missing_symbol_count = 0
    for exchange, result in (("TWSE", twse_result), ("TPEX", tpex_result)):
        allowed_symbols = universe_by_exchange[exchange]
        if result.error_message:
            errors.append(
                {
                    "source_name": result.source_name,
                    "message": result.error_message,
                }
            )
            missing_symbol_count += len(allowed_symbols)
            continue

        filtered = _filter_batch_frame_to_universe(
            result.dataframe,
            allowed_symbols=allowed_symbols,
        )
        validated_filtered, _ = validate_ohlcv_with_report(
            filtered,
            label=f"{exchange.lower()}_batch_missing",
        )
        missing_symbol_count += len(allowed_symbols - set(validated_filtered["symbol"]))
        filtered_frames.append(_attach_frame_metadata(filtered, result.metadata))

    combined_df = (
        pd.concat(filtered_frames, ignore_index=True)
        if filtered_frames
        else pd.DataFrame()
    )
    load_summary = load_to_db(combined_df)
    summary = {
        "market": MARKET_TW,
        "trading_date": trading_date.isoformat(),
        "refresh_universe": refresh_universe,
        "universe_count": universe_count,
        "twse_rows": twse_result.raw_row_count,
        "tpex_rows": tpex_result.raw_row_count,
        "filtered_rows": len(combined_df),
        "missing_symbol_count": missing_symbol_count,
        "upserted_rows": load_summary["upserted_rows"],
        "validated_rows": load_summary["validated_rows"],
        "official_overrides": load_summary["official_overrides"],
        "raw_payload_ids": [
            metadata.raw_payload_id
            for metadata in (twse_result.metadata, tpex_result.metadata)
            if metadata is not None and metadata.raw_payload_id is not None
        ],
        "errors": errors,
    }
    if universe_refresh_summary is not None:
        summary["universe_refresh"] = universe_refresh_summary
    return summary


def ingest_symbol(
    symbol: str,
    market: str = MARKET_TW,
    years: int = 5,
    date_str: str | None = None,
) -> dict:
    market_code = (market or MARKET_TW).upper()
    summary = {
        "symbol": symbol,
        "market": market_code,
        "backfill": {},
        "daily_update": {},
        "minute_supplement": {},
    }

    backfill_df, backfill_meta = backfill_history(
        symbol=symbol, years=years, market=market_code
    )
    summary["backfill"] = _attach_stage_metadata(
        load_to_db(backfill_df, metadata=backfill_meta),
        backfill_meta,
    )

    if market_code == MARKET_TW:
        daily_df, daily_meta = scrape_daily_twse(symbol=symbol, date_str=date_str)
        summary["daily_update"] = _attach_stage_metadata(
            load_to_db(daily_df, metadata=daily_meta),
            daily_meta,
        )
    else:
        summary["daily_update"] = _attach_stage_metadata(
            {
                "input_rows": 0,
                "validated_rows": 0,
                "dropped_rows": 0,
                "duplicates_removed": 0,
                "null_rows_removed": 0,
                "invalid_rows_removed": 0,
                "gap_warnings": 0,
                "upserted_rows": 0,
                "official_overrides": 0,
            },
            None,
        )

    summary["minute_supplement"] = supplement_yahoo_minute_history(
        symbol=symbol,
        market=market_code,
        date_str=date_str,
    )

    logger.info("Ingest completed summary=%s", summary)
    return summary


if __name__ == "__main__":
    # Use `alembic upgrade head` to create/migrate tables.
    print(
        "Run 'uv run alembic upgrade head' to create or migrate database tables before ingesting."
    )

    symbol = os.getenv("INGEST_SYMBOL", "2330")
    market = os.getenv("INGEST_MARKET", MARKET_TW).upper()
    years = int(os.getenv("INGEST_YEARS", "5"))
    date_str = os.getenv("INGEST_DATE")

    logger.info(
        "Starting ingest symbol=%s market=%s years=%s date_override=%s",
        symbol,
        market,
        years,
        date_str,
    )
    print(ingest_symbol(symbol=symbol, market=market, years=years, date_str=date_str))
