from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.official_event_crawler_service import crawl_lifecycle_records


def main() -> int:
    summary = crawl_lifecycle_records()
    print(json.dumps(summary, ensure_ascii=True, default=str))
    if summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
