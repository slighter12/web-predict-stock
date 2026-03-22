from __future__ import annotations

import json

from backend.market_data.services.official_crawlers import crawl_important_events


def main() -> int:
    summary = crawl_important_events()
    print(json.dumps(summary, ensure_ascii=True, default=str))
    if summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
