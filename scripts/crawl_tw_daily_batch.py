from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from backend.market_data.services.ingestion import ingest_tw_market_batch

_TW_TZ = ZoneInfo("Asia/Taipei")


def _parse_trading_date(value: str | None) -> date:
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
    raise ValueError("INGEST_DATE must be YYYY-MM-DD or YYYYMMDD.")


def main() -> int:
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
        start_date = _parse_trading_date(args.start_date)
        end_date = _parse_trading_date(args.end_date)
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
        "errors": [],
    }
    for index, trading_date in enumerate(trading_dates):
        trading_date_text = trading_date.isoformat()
        aggregate["attempted_dates"].append(trading_date_text)
        try:
            summary = ingest_tw_market_batch(
                trading_date=trading_date,
                refresh_universe=args.refresh_universe and index == 0,
            )
        except Exception as exc:
            aggregate["failed_dates"].append(trading_date_text)
            aggregate["errors"].append(
                {
                    "trading_date": trading_date_text,
                    "source_name": "batch",
                    "message": str(exc) or "Batch ingestion failed.",
                }
            )
            if index + 1 < len(trading_dates):
                time.sleep(args.delay_seconds)
            continue
        aggregate["upserted_rows"] += int(summary["upserted_rows"])
        if summary.get("status") == "skipped_non_trading_day":
            aggregate["skipped_non_trading_dates"].append(trading_date_text)
        elif summary["errors"]:
            aggregate["failed_dates"].append(trading_date_text)
            aggregate["errors"].extend(
                {"trading_date": trading_date_text, **error}
                for error in summary["errors"]
            )
        else:
            aggregate["succeeded_dates"].append(trading_date_text)
        if index + 1 < len(trading_dates):
            time.sleep(args.delay_seconds)

    print(json.dumps(aggregate, ensure_ascii=True, default=str))
    return 1 if aggregate["failed_dates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
