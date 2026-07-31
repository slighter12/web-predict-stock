from __future__ import annotations

import json
import re
from zoneinfo import ZoneInfo

SOURCE_TWSE = "twse"
SOURCE_TWSE_MI_INDEX = "twse_mi_index"
SOURCE_TPEX_AFTERTRADING_OTC = "tpex_aftertrading_otc"
TW_TIMEZONE = ZoneInfo("Asia/Taipei")
OFFICIAL_SOURCES = (
    SOURCE_TWSE,
    SOURCE_TWSE_MI_INDEX,
    SOURCE_TPEX_AFTERTRADING_OTC,
)


def payload_declares_no_data(payload_body: str | None) -> bool:
    try:
        payload = json.loads(payload_body)
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    detail = " ".join(
        str(payload.get(key) or "") for key in ("stat", "message", "msg")
    ).lower()
    if (
        "沒有符合條件" in detail
        or "查無資料" in detail
        or re.search(r"\bno data\b", detail)
    ):
        return True
    if str(payload.get("stat") or "").strip().lower() != "ok":
        return False
    tables = [item for item in (payload.get("tables") or []) if isinstance(item, dict)]
    if not tables:
        return False
    for table in tables:
        if table.get("data") != []:
            return False
        total_count = table.get("totalCount")
        if isinstance(total_count, bool):
            return False
        try:
            if float(total_count) != 0:
                return False
        except (TypeError, ValueError):
            return False
    return True
