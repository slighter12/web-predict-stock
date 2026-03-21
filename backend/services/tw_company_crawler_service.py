from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

import requests

from ..errors import DataAccessError, ExternalFetchError, UnsupportedConfigurationError
from ..repositories.raw_ingest_repository import (
    FETCH_STATUS_FAILED,
    FETCH_STATUS_SUCCESS,
    persist_raw_ingest_record,
)
from .tw_company_profile_service import (
    count_active_tw_company_profiles,
    save_tw_company_profile,
)
from ..time_utils import utc_now

logger = logging.getLogger(__name__)

TWSE_COMPANY_SOURCE_URL_ENV = "TWSE_COMPANY_SOURCE_URL"
TPEX_COMPANY_SOURCE_URL_ENV = "TPEX_COMPANY_SOURCE_URL"
TWSE_COMPANY_SOURCE_URL_DEFAULT = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANY_SOURCE_URL_DEFAULT = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
TWSE_COMPANY_SOURCE_NAME = "twse_company_profile"
TPEX_COMPANY_SOURCE_NAME = "tpex_company_profile"
TW_COMPANY_PARSER_VERSION = "tw_company_profile_v1"
TW_COMPANY_SYMBOL = "TW_COMPANY_UNIVERSE"
_PAYLOAD_RECORD_KEYS = ("records", "data", "items", "result", "results", "response")


def _describe_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = [str(key) for key in payload.keys()]
        return ",".join(keys[:10]) if keys else "<empty>"
    return type(payload).__name__


def _extract_record_list(payload: Any, *, depth: int = 0) -> list[dict[str, Any]] | None:
    if depth > 4:
        return None
    if isinstance(payload, list):
        records = [item for item in payload if isinstance(item, dict)]
        return records or None
    if not isinstance(payload, dict):
        return None
    for key in _PAYLOAD_RECORD_KEYS:
        if key not in payload:
            continue
        records = _extract_record_list(payload.get(key), depth=depth + 1)
        if records is not None:
            return records
    return None


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    records = _extract_record_list(payload)
    if records is not None:
        return records
    if isinstance(payload, list):
        raise UnsupportedConfigurationError(
            "TW company crawler payload contains no record objects."
        )
    raise UnsupportedConfigurationError(
        "TW company crawler payload format is unsupported. "
        f"top_level={_describe_payload(payload)}"
    )


def _first_value(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_listing_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.strip().replace("/", "-")
    if len(normalized) == 8 and normalized.isdigit():
        normalized = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _fetch_company_feed(
    *,
    url_env: str,
    default_url: str,
    source_name: str,
) -> tuple[int, list[dict[str, Any]]]:
    url = os.getenv(url_env, default_url)
    if not url:
        raise UnsupportedConfigurationError(f"{url_env} is required.")
    payload_body = ""
    fetch_timestamp = utc_now()
    expected_context = f"source={source_name};market=TW"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException as exc:
        try:
            persist_raw_ingest_record(
                source_name=source_name,
                symbol=TW_COMPANY_SYMBOL,
                market="TW",
                parser_version=TW_COMPANY_PARSER_VERSION,
                fetch_status=FETCH_STATUS_FAILED,
                expected_symbol_context=expected_context,
                payload_body=payload_body,
                fetch_timestamp=fetch_timestamp,
            )
        except DataAccessError:
            logger.warning("Failed to record company crawler fetch failure")
        raise ExternalFetchError(f"Failed to fetch TW company feed: {exc}") from exc

    try:
        payload = json.loads(payload_body)
        records = _extract_records(payload)
    except Exception as exc:
        try:
            persist_raw_ingest_record(
                source_name=source_name,
                symbol=TW_COMPANY_SYMBOL,
                market="TW",
                parser_version=TW_COMPANY_PARSER_VERSION,
                fetch_status=FETCH_STATUS_FAILED,
                expected_symbol_context=expected_context,
                payload_body=payload_body,
                fetch_timestamp=fetch_timestamp,
            )
        except DataAccessError:
            logger.warning("Failed to record company crawler parse failure")
        raise UnsupportedConfigurationError(
            "TW company crawler payload parsing failed."
        ) from exc

    raw_payload_id = persist_raw_ingest_record(
        source_name=source_name,
        symbol=TW_COMPANY_SYMBOL,
        market="TW",
        parser_version=TW_COMPANY_PARSER_VERSION,
        fetch_status=FETCH_STATUS_SUCCESS,
        expected_symbol_context=expected_context,
        payload_body=payload_body,
        fetch_timestamp=fetch_timestamp,
    )
    return raw_payload_id, records


def _build_profile_payload(
    *,
    item: dict[str, Any],
    exchange: str,
    board: str,
    source_name: str,
    raw_payload_id: int,
    archive_reference: str,
) -> dict[str, Any]:
    symbol = _first_value(
        item,
        "CompanyCode",
        "SecuritiesCompanyCode",
        "公司代碼",
        "公司代號",
        "股票代號",
        "代號",
        "Code",
    )
    company_name = _first_value(
        item,
        "CompanyName",
        "公司名稱",
        "股票名稱",
        "簡稱",
        "名稱",
        "公司簡稱",
        "Name",
    )
    if symbol is None or company_name is None:
        raise ValueError("Company profile is missing symbol or company_name.")

    listing_date = _parse_listing_date(
        _first_value(
            item,
            "ListingDate",
            "上市日期",
            "上櫃日期",
            "掛牌日期",
        )
    )
    trading_status = (
        _first_value(
            item,
            "TradingStatus",
            "交易狀態",
            "狀態",
            "Status",
        )
        or "active"
    )
    notes = _first_value(item, "MarketCategory", "市場別", "備註", "Note")
    return {
        "symbol": symbol,
        "market": "TW",
        "exchange": exchange,
        "board": board,
        "company_name": company_name,
        "isin_code": _first_value(item, "ISINCode", "ISIN", "國際證券辨識號碼"),
        "industry_category": _first_value(
            item, "Industry", "IndustryCategory", "產業別", "產業類別"
        ),
        "listing_date": listing_date,
        "trading_status": "active"
        if trading_status.lower() in {"active", "listed", "trading", "正常"}
        else trading_status.lower(),
        "source_name": source_name,
        "raw_payload_id": raw_payload_id,
        "archive_object_reference": archive_reference,
        "notes": notes,
    }


def _profile_identity(payload: dict[str, Any]) -> tuple[str, str]:
    return payload["exchange"], payload["symbol"]


def _profile_completeness_score(payload: dict[str, Any]) -> int:
    tracked_fields = (
        "company_name",
        "isin_code",
        "industry_category",
        "listing_date",
        "trading_status",
        "notes",
    )
    return sum(1 for field in tracked_fields if payload.get(field) not in (None, ""))


def _profile_sort_key(payload: dict[str, Any]) -> tuple[int, str]:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return (_profile_completeness_score(payload), canonical)


def _dedupe_profile_payloads(
    payloads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_symbol_count = 0
    conflict_count = 0
    overwritten_count = 0
    for payload in payloads:
        key = _profile_identity(payload)
        current = selected.get(key)
        if current is None:
            selected[key] = payload
            continue
        duplicate_symbol_count += 1
        if _profile_sort_key(payload) > _profile_sort_key(current):
            if payload != current:
                conflict_count += 1
                overwritten_count += 1
            selected[key] = payload
            continue
        if payload != current:
            conflict_count += 1
    deduped_payloads = [
        selected[key] for key in sorted(selected.keys(), key=lambda item: (item[0], item[1]))
    ]
    return deduped_payloads, {
        "duplicate_symbol_count": duplicate_symbol_count,
        "conflict_count": conflict_count,
        "overwritten_count": overwritten_count,
    }


def _crawl_single_source(
    *,
    url_env: str,
    default_url: str,
    source_name: str,
    exchange: str,
    board: str,
) -> dict[str, Any]:
    raw_payload_id, records = _fetch_company_feed(
        url_env=url_env,
        default_url=default_url,
        source_name=source_name,
    )
    archive_reference = f"raw_ingest_audit:{raw_payload_id}"
    built_profiles: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in records:
        try:
            built_profiles.append(
                _build_profile_payload(
                    item=item,
                    exchange=exchange,
                    board=board,
                    source_name=source_name,
                    raw_payload_id=raw_payload_id,
                    archive_reference=archive_reference,
                )
            )
        except Exception as exc:
            symbol = (
                _first_value(item, "公司代號", "股票代號", "公司代碼", "CompanyCode")
                or "unknown"
            )
            errors.append(f"exchange={exchange} symbol={symbol}: {exc}")
    deduped_profiles, dedupe_summary = _dedupe_profile_payloads(built_profiles)
    upserted_count = 0
    created_count = 0
    updated_count = 0
    noop_count = 0
    for payload in deduped_profiles:
        try:
            saved = save_tw_company_profile(payload)
            upserted_count += 1
            write_action = saved.get("write_action")
            if write_action == "created":
                created_count += 1
            elif write_action == "updated":
                updated_count += 1
            else:
                noop_count += 1
        except Exception as exc:
            errors.append(
                f"exchange={payload['exchange']} symbol={payload['symbol']}: {exc}"
            )
    return {
        "source_name": source_name,
        "raw_payload_id": raw_payload_id,
        "processed_count": len(records),
        "upserted_count": upserted_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "noop_count": noop_count,
        "duplicate_symbol_count": dedupe_summary["duplicate_symbol_count"],
        "conflict_count": dedupe_summary["conflict_count"],
        "overwritten_count": dedupe_summary["overwritten_count"],
        "errors": errors,
    }


def crawl_tw_company_profiles(*, include_tpex: bool = True) -> dict[str, Any]:
    summaries = [
        _crawl_single_source(
            url_env=TWSE_COMPANY_SOURCE_URL_ENV,
            default_url=TWSE_COMPANY_SOURCE_URL_DEFAULT,
            source_name=TWSE_COMPANY_SOURCE_NAME,
            exchange="TWSE",
            board="listed",
        )
    ]
    if include_tpex:
        summaries.append(
            _crawl_single_source(
                url_env=TPEX_COMPANY_SOURCE_URL_ENV,
                default_url=TPEX_COMPANY_SOURCE_URL_DEFAULT,
                source_name=TPEX_COMPANY_SOURCE_NAME,
                exchange="TPEX",
                board="otc",
            )
        )

    return {
        "market": "TW",
        "source_names": [item["source_name"] for item in summaries],
        "raw_payload_ids": [item["raw_payload_id"] for item in summaries],
        "processed_count": sum(item["processed_count"] for item in summaries),
        "upserted_count": sum(item["upserted_count"] for item in summaries),
        "created_count": sum(item["created_count"] for item in summaries),
        "updated_count": sum(item["updated_count"] for item in summaries),
        "noop_count": sum(item["noop_count"] for item in summaries),
        "duplicate_symbol_count": sum(
            item["duplicate_symbol_count"] for item in summaries
        ),
        "conflict_count": sum(item["conflict_count"] for item in summaries),
        "overwritten_count": sum(item["overwritten_count"] for item in summaries),
        "active_symbol_count": count_active_tw_company_profiles(),
        "errors": [error for item in summaries for error in item["errors"]],
    }
