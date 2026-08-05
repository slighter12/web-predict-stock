from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from backend.market_data.services.ingestion import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_SKIPPED_NON_TRADING_DAY,
    BATCH_STATUS_SUCCEEDED,
    ingest_tw_market_batch,
)
from scripts._logging import configure_cli_logging

_TW_TZ = ZoneInfo("Asia/Taipei")


def _print_progress(
    *,
    trading_date: str,
    status: str,
    upserted_rows: int,
    error_count: int,
) -> None:
    print(
        json.dumps(
            {
                "event": "tw_market_batch_progress",
                "trading_date": trading_date,
                "status": status,
                "upserted_rows": upserted_rows,
                "error_count": error_count,
            },
            ensure_ascii=True,
        ),
        file=sys.stderr,
        flush=True,
    )


def _parse_trading_date(
    value: str | None, *, argument_name: str = "INGEST_DATE"
) -> date:
    if not value:
        return datetime.now(_TW_TZ).date()
    normalized = value.strip()
    for parser in (
        date.fromisoformat,
        lambda item: datetime.strptime(item, "%Y%m%d").date(),
    ):
        try:
            return parser(normalized)
        except ValueError:
            continue
    raise ValueError(f"{argument_name} must be YYYY-MM-DD or YYYYMMDD.")


def main() -> int:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Ingest TW market daily batch data.")
    parser.add_argument("trading_date", nargs="?")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        default=os.getenv("REFRESH_UNIVERSE", "").lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args()

    if bool(args.start_date) != bool(args.end_date):
        parser.error("--start-date and --end-date must be provided together.")
    if args.start_date and args.trading_date:
        parser.error("trading_date cannot be combined with a date range.")
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must be nonnegative.")

    if not args.start_date:
        trading_date_value = args.trading_date or os.getenv("INGEST_DATE")
        try:
            trading_date = _parse_trading_date(trading_date_value)
        except ValueError as exc:
            parser.error(str(exc))
        summary = ingest_tw_market_batch(
            trading_date=trading_date,
            refresh_universe=args.refresh_universe,
        )
        print(json.dumps(summary, ensure_ascii=True, default=str))
        return 1 if summary["errors"] else 0

    try:
        start_date = _parse_trading_date(
            args.start_date, argument_name="--start-date"
        )
        end_date = _parse_trading_date(args.end_date, argument_name="--end-date")
    except ValueError as exc:
        parser.error(str(exc))
    if start_date > end_date:
        parser.error("--start-date must not be after --end-date.")

    trading_dates = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:
            trading_dates.append(current_date)
        current_date += timedelta(days=1)

    aggregate = {
        "market": "TW",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "attempted_dates": [],
        "succeeded_dates": [],
        "skipped_non_trading_dates": [],
        "failed_dates": [],
        "upserted_rows": 0,
        "universe_refresh_succeeded": None,
        "errors": [],
    }
    refresh_attempts_left = 3 if args.refresh_universe else 0
    for index, trading_date in enumerate(trading_dates):
        trading_date_text = trading_date.isoformat()
        aggregate["attempted_dates"].append(trading_date_text)
        should_refresh = refresh_attempts_left > 0
        if should_refresh:
            refresh_attempts_left -= 1
            aggregate["universe_refresh_succeeded"] = False
        summary_upserted_rows = 0
        try:
            summary = ingest_tw_market_batch(
                trading_date=trading_date,
                refresh_universe=should_refresh,
            )
            summary_upserted_rows = int(summary["upserted_rows"])
            aggregate["upserted_rows"] += summary_upserted_rows
            summary_errors = summary["errors"]
            if not isinstance(summary_errors, list):
                raise TypeError("Batch summary errors must be a list.")
            summary_status = summary["status"]
            dated_errors = [
                {"trading_date": trading_date_text, **error}
                for error in summary_errors
            ]
        except Exception as exc:
            aggregate["failed_dates"].append(trading_date_text)
            aggregate["errors"].append(
                {
                    "trading_date": trading_date_text,
                    "source_name": "batch",
                    "error_type": type(exc).__name__,
                    "message": "Batch ingestion failed.",
                }
            )
            _print_progress(
                trading_date=trading_date_text,
                status=BATCH_STATUS_FAILED,
                upserted_rows=summary_upserted_rows,
                error_count=1,
            )
            if index + 1 < len(trading_dates):
                time.sleep(args.delay_seconds)
            continue
        if should_refresh:
            refresh_failed = any(
                isinstance(error, dict)
                and error.get("source_name") == "universe_refresh"
                for error in summary_errors
            )
            if not refresh_failed:
                aggregate["universe_refresh_succeeded"] = True
                refresh_attempts_left = 0
        if summary_errors:
            aggregate["failed_dates"].append(trading_date_text)
            aggregate["errors"].extend(dated_errors)
            progress_status = BATCH_STATUS_FAILED
        elif summary_status == BATCH_STATUS_SKIPPED_NON_TRADING_DAY:
            aggregate["skipped_non_trading_dates"].append(trading_date_text)
            progress_status = BATCH_STATUS_SKIPPED_NON_TRADING_DAY
        elif summary_status == BATCH_STATUS_SUCCEEDED:
            aggregate["succeeded_dates"].append(trading_date_text)
            progress_status = BATCH_STATUS_SUCCEEDED
        else:
            aggregate["failed_dates"].append(trading_date_text)
            progress_status = BATCH_STATUS_FAILED
            dated_errors = [
                {
                    "trading_date": trading_date_text,
                    "source_name": "batch",
                    "message": f"Batch ingestion status={summary_status}.",
                }
            ]
            aggregate["errors"].extend(dated_errors)
        _print_progress(
            trading_date=trading_date_text,
            status=progress_status,
            upserted_rows=summary_upserted_rows,
            error_count=len(dated_errors),
        )
        if index + 1 < len(trading_dates):
            time.sleep(args.delay_seconds)

    print(json.dumps(aggregate, ensure_ascii=True, default=str))
    return 1 if aggregate["failed_dates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
