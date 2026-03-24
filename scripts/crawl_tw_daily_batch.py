from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
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
    parser.add_argument("trading_date", nargs="?", default=os.getenv("INGEST_DATE"))
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        default=os.getenv("REFRESH_UNIVERSE", "").lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args()

    summary = ingest_tw_market_batch(
        trading_date=_parse_trading_date(args.trading_date),
        refresh_universe=args.refresh_universe,
    )
    print(json.dumps(summary, ensure_ascii=True, default=str))
    if summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
