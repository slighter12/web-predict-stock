from __future__ import annotations

import calendar
from datetime import date


def resolve_schedule_slot_date(year: int, month: int, day_of_month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(1, day_of_month), last_day))
