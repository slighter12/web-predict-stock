import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from backend.database import DailyOHLCV, create_tables, engine
except ImportError:
    print("Error: Could not import from backend.database. Make sure the backend directory is in the Python path.")
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
        logger.warning("Missing columns in OHLCV data label=%s missing=%s", label, missing)
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


def scrape_twse_data(symbol: str, date_str: str | None = None) -> pd.DataFrame:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={symbol}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.exception("TWSE request failed symbol=%s date=%s", symbol, date_str)
        return pd.DataFrame()

    try:
        data = response.json()
        if data.get("stat") != "OK":
            logger.warning(
                "TWSE returned non-OK status symbol=%s date=%s detail=%s",
                symbol,
                date_str,
                data,
            )
            return pd.DataFrame()

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
                df[col].astype(str).str.replace(",", ""), errors="coerce"
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
        logger.info(
            "Scraped TWSE rows=%s symbol=%s month=%s", len(df), symbol, date_str[:6]
        )
        cleaned, _ = validate_ohlcv_with_report(df, label=f"{symbol}:{SOURCE_TWSE}")
        return cleaned
    except Exception:
        logger.exception(
            "TWSE payload parsing failed symbol=%s date=%s", symbol, date_str
        )
        return pd.DataFrame()


def load_to_db(df: pd.DataFrame) -> dict:
    validated_df, quality = validate_ohlcv_with_report(df, label="load_to_db")
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
                            date, symbol, market, source, open, high, low, close, volume
                        )
                        SELECT date, symbol, market, source, open, high, low, close, volume
                        FROM {temp_table_name}
                        ON CONFLICT (date, symbol) DO UPDATE SET
                            market = EXCLUDED.market,
                            source = EXCLUDED.source,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
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


def scrape_daily_twse(symbol: str, date_str: str | None = None) -> pd.DataFrame:
    month_df = scrape_twse_data(symbol=symbol, date_str=date_str)
    if month_df.empty:
        return month_df

    latest_date = max(month_df["date"])
    latest = month_df[month_df["date"] == latest_date].copy()
    logger.info("Selected latest TWSE daily row symbol=%s date=%s", symbol, latest_date)
    return latest


def backfill_history(
    symbol: str, years: int = 5, market: str = MARKET_TW
) -> pd.DataFrame:
    if years < 1:
        raise ValueError("years must be >= 1")

    ticker_symbol = to_yfinance_ticker(symbol, market)
    start_date = datetime.utcnow() - timedelta(days=365 * years)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start_date, auto_adjust=False, actions=False)
    except Exception:
        logger.exception(
            "Failed to fetch yfinance data symbol=%s market=%s", symbol, market
        )
        return pd.DataFrame()

    if hist.empty:
        logger.warning("No yfinance data returned symbol=%s market=%s", symbol, market)
        return pd.DataFrame()

    hist = hist.reset_index()
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
    logger.info(
        "Fetched yfinance history rows=%s symbol=%s market=%s",
        len(hist),
        symbol,
        market,
    )
    cleaned, _ = validate_ohlcv_with_report(hist, label=f"{symbol}:{SOURCE_YFINANCE}")
    return cleaned


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

    backfill_df = backfill_history(symbol=symbol, years=years, market=market_code)
    summary["backfill"] = load_to_db(backfill_df)

    if market_code == MARKET_TW:
        daily_df = scrape_daily_twse(symbol=symbol, date_str=date_str)
        summary["daily_update"] = load_to_db(daily_df)
    else:
        summary["daily_update"] = {
            "input_rows": 0,
            "validated_rows": 0,
            "dropped_rows": 0,
            "duplicates_removed": 0,
            "null_rows_removed": 0,
            "invalid_rows_removed": 0,
            "gap_warnings": 0,
            "upserted_rows": 0,
            "official_overrides": 0,
        }

    logger.info("Ingest completed summary=%s", summary)
    return summary


if __name__ == "__main__":
    create_tables()

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
