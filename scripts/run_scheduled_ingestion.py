from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.services.scheduled_ingestion_service import (
    dispatch_due_scheduled_ingestions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    summary = dispatch_due_scheduled_ingestions()
    print(json.dumps(summary, ensure_ascii=True, default=str))
    if int(summary["failed_count"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
