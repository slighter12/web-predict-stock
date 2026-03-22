import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import partial
from io import StringIO

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from backend.database import DailyOHLCV, RawIngestAudit, engine
    from backend.market_data.services.tick_archive_provider import (
        _SSLContextAdapter,
        _build_ssl_context,
        _ca_auto_download_enabled,
        _download_ca_bundle,
        _insecure_tls_fallback_enabled,
        _resolve_tls_verify,
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
MARKET_TW = "TW"
MARKET_US = "US"


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
FETCH_STATUS_SUCCESS = "success"
FETCH_STATUS_FAILED = "failed"


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
        response = _request_twse_daily_report(url=url, headers=headers, timeout_seconds=30)
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
    verify = _resolve_tls_verify()
    try:
        return _perform_tls_request(
            url=url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            verify=verify,
        )
    except requests.exceptions.SSLError:
        response = None
        if _ca_auto_download_enabled():
            try:
                downloaded_verify = _download_ca_bundle()
                response = _perform_tls_request(
                    url=url,
                    headers=headers,
                    timeout_seconds=timeout_seconds,
                    verify=downloaded_verify,
                )
            except requests.RequestException:
                logger.exception("Failed TWSE daily report fetch after CA download url=%s", url)
            except Exception:
                logger.exception("Failed to download TWSE CA bundle for url=%s", url)

        if response is None and _insecure_tls_fallback_enabled():
            logger.warning("Retrying TWSE daily report without TLS verification url=%s", url)
            response = _perform_tls_request(
                url=url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                verify=False,
            )

        if response is None:
            raise
        return response


def _perform_tls_request(
    *,
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    verify: bool | str,
) -> requests.Response:
    if verify is False:
        return requests.get(url, headers=headers, timeout=timeout_seconds, verify=False)

    session = requests.Session()
    session.mount("https://", _SSLContextAdapter(_build_ssl_context(verify)))
    return session.get(url, headers=headers, timeout=timeout_seconds)


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
    try:
        validated_df = validated_df.copy()
        validated_df["raw_payload_id"] = raw_payload_id
        validated_df["archive_object_reference"] = archive_object_reference
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
                        WHERE incoming.source = :official_source
                          AND existing.source != :official_source
                        """
                    ),
                    {"official_source": SOURCE_TWSE},
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
                        WHERE EXCLUDED.source = :official_source
                           OR {DailyOHLCV.__tablename__}.source IS NULL
                           OR {DailyOHLCV.__tablename__}.source != :official_source
                        """
                    ),
                    {"official_source": SOURCE_TWSE},
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
