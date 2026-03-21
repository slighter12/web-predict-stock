from __future__ import annotations

import logging

from ..repositories.tw_company_profile_repository import (
    count_tw_company_profiles,
    list_tw_company_profiles,
    upsert_tw_company_profile,
)
from ._normalization import clean_optional_text, clean_required_text

logger = logging.getLogger(__name__)


def save_tw_company_profile(payload: dict) -> dict:
    normalized = dict(payload)
    normalized["symbol"] = clean_required_text(payload["symbol"]).upper()
    normalized["market"] = clean_required_text(payload.get("market", "TW")).upper()
    normalized["exchange"] = clean_required_text(payload["exchange"]).upper()
    normalized["board"] = clean_required_text(payload["board"]).lower()
    normalized["company_name"] = clean_required_text(payload["company_name"])
    normalized["trading_status"] = clean_required_text(
        payload.get("trading_status", "active")
    ).lower()
    normalized["source_name"] = clean_required_text(payload["source_name"])
    normalized["isin_code"] = clean_optional_text(payload.get("isin_code"))
    normalized["industry_category"] = clean_optional_text(
        payload.get("industry_category")
    )
    normalized["archive_object_reference"] = clean_optional_text(
        payload.get("archive_object_reference")
    )
    normalized["notes"] = clean_optional_text(payload.get("notes"))
    return upsert_tw_company_profile(normalized)


def list_active_tw_company_profiles(*, limit: int = 500, offset: int = 0) -> list[dict]:
    records = list_tw_company_profiles(
        limit=limit,
        offset=offset,
        trading_status="active",
    )
    logger.info(
        "Listed active TW company profiles count=%s limit=%s offset=%s",
        len(records),
        limit,
        offset,
    )
    return records


def count_active_tw_company_profiles() -> int:
    total = count_tw_company_profiles(trading_status="active")
    logger.info("Counted active TW company profiles total=%s", total)
    return total
