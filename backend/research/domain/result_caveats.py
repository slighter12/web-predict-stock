from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE = (
    "TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE"
)
TW_POINT_IN_TIME_MEMBERSHIP_WARNING = (
    "TW company-universe membership is current-status only, not point-in-time. "
    "If the result window reaches before local ingestion began, already-delisted "
    "symbols may be absent from price coverage and returns may be optimistic by an "
    "unquantified amount."
)
INVALID_DYNAMIC_EFFECTIVE_STRATEGY_METADATA = (
    "invalid_dynamic_effective_strategy_metadata"
)
DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE = (
    "DYNAMIC_STRATEGY_METADATA_UNAVAILABLE"
)
DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_MESSAGE = (
    "Dynamic strategy metadata is unavailable; replay, prospective execution, "
    "and full comparison are disabled."
)


def _market_value(
    market: Any,
    request_payload: Mapping[str, Any] | None,
) -> str | None:
    value = market
    if value is None and request_payload is not None:
        value = request_payload.get("market")
    return str(value).upper() if value is not None else None


def is_tw_result(
    *,
    market: Any,
    request_payload: Mapping[str, Any] | None,
) -> bool:
    return _market_value(market, request_payload) == "TW"


def warnings_with_result_caveats(
    warnings: Sequence[str] | None,
    *,
    status: str | None,
    market: Any,
    request_payload: Mapping[str, Any] | None,
) -> list[str]:
    result = list(warnings or [])
    if status == "succeeded" and is_tw_result(
        market=market,
        request_payload=request_payload,
    ):
        result = [
            item for item in result if item != TW_POINT_IN_TIME_MEMBERSHIP_WARNING
        ]
        result.append(TW_POINT_IN_TIME_MEMBERSHIP_WARNING)
    return result


def tw_point_in_time_membership_caveat(
    *,
    market: Any,
    request_payload: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    if not is_tw_result(market=market, request_payload=request_payload):
        return None
    return {
        "code": TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE,
        "label": TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
        "severity": "note",
    }
