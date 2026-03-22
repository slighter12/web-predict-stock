from __future__ import annotations

import json

from backend.market_data.services.recovery import dispatch_due_recovery_drills


def main() -> int:
    summary = dispatch_due_recovery_drills()
    print(json.dumps(summary, ensure_ascii=True, default=str))
    if int(summary["failed_count"]) > 0 or int(summary["error_count"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
