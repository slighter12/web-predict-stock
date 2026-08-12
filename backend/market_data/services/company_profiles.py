from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.market_data.repositories.company_profiles import (
    count_tw_company_profiles,
    list_tw_company_profiles,
    upsert_tw_company_profile,
)
from backend.market_data.repositories.raw_ingest import (
    FETCH_STATUS_SUCCESS,
    get_raw_ingest_record,
)
from backend.market_data.services._normalization import (
    clean_optional_text,
    clean_required_text,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompanyProfileSource:
    url: str
    source_name: str
    exchange: str
    board: str


TWSE_COMPANY_SOURCE = CompanyProfileSource(
    url="https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
    source_name="twse_company_profile",
    exchange="TWSE",
    board="listed",
)
TPEX_COMPANY_SOURCE = CompanyProfileSource(
    url="https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
    source_name="tpex_company_profile",
    exchange="TPEX",
    board="otc",
)
TW_COMPANY_SOURCES = (TWSE_COMPANY_SOURCE, TPEX_COMPANY_SOURCE)
_SOURCE_BY_NAME = {source.source_name: source for source in TW_COMPANY_SOURCES}
TW_COMPANY_PARSER_VERSION = "tw_company_profile_v1"
TW_COMPANY_SYMBOL = "TW_COMPANY_UNIVERSE"
_PAYLOAD_RECORD_KEYS = ("records", "data", "items", "result", "results", "response")


@dataclass(frozen=True)
class CompanyProfileSaveOutcome:
    payload: dict
    saved: dict | None
    error: Exception | None


def _extract_record_list(
    payload: Any, *, depth: int = 0
) -> list[dict[str, Any]] | None:
    if depth > 4:
        return None
    if isinstance(payload, list):
        records = [item for item in payload if isinstance(item, dict)]
        return records or None
    if not isinstance(payload, dict):
        return None
    for key in _PAYLOAD_RECORD_KEYS:
        if key in payload:
            records = _extract_record_list(payload[key], depth=depth + 1)
            if records is not None:
                return records
    return None


def _first_value(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is not None and (text := str(value).strip()):
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
            "DateOfListing",
            "上市日期",
            "上櫃日期",
            "掛牌日期",
        )
    )
    trading_status = _first_value(
        item,
        "TradingStatus",
        "交易狀態",
        "狀態",
        "Status",
    )
    if trading_status is not None and trading_status.lower() not in {
        "active",
        "listed",
        "trading",
        "正常",
    }:
        raise ValueError("Company profile status is not active.")
    return {
        "symbol": symbol,
        "market": "TW",
        "exchange": exchange,
        "board": board,
        "company_name": company_name,
        "isin_code": _first_value(item, "ISINCode", "ISIN", "國際證券辨識號碼"),
        "industry_category": _first_value(
            item,
            "Industry",
            "IndustryCategory",
            "SecuritiesIndustryCode",
            "產業別",
            "產業類別",
        ),
        "listing_date": listing_date,
        "trading_status": "active",
        "source_name": source_name,
        "raw_payload_id": raw_payload_id,
        "archive_object_reference": archive_reference,
        "notes": _first_value(item, "MarketCategory", "市場別", "備註", "Note"),
    }


def _profile_fingerprint(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)


def _validate_company_profile_provenance(
    *, payload: dict, source: CompanyProfileSource
) -> Any:
    raw_payload_id = payload.get("raw_payload_id")
    if (
        not isinstance(raw_payload_id, int)
        or isinstance(raw_payload_id, bool)
        or raw_payload_id <= 0
    ):
        raise ValueError("TW company profile raw_payload_id must be a positive int.")
    expected_archive_reference = f"raw_ingest_audit:{raw_payload_id}"
    if payload.get("archive_object_reference") != expected_archive_reference:
        raise ValueError("TW company profile archive reference is invalid.")

    raw_record = get_raw_ingest_record(raw_payload_id)
    expected_context = f"source={source.source_name};market=TW"
    expected_provenance = {
        "source_name": source.source_name,
        "market": "TW",
        "symbol": TW_COMPANY_SYMBOL,
        "parser_version": TW_COMPANY_PARSER_VERSION,
        "fetch_status": FETCH_STATUS_SUCCESS,
        "expected_symbol_context": expected_context,
    }
    if any(
        getattr(raw_record, field, None) != expected
        for field, expected in expected_provenance.items()
    ):
        raise ValueError("TW company profile raw ingest provenance is invalid.")
    return raw_record


def _normalize_company_profile(payload: dict) -> tuple[dict, CompanyProfileSource]:
    normalized = dict(payload)
    normalized["symbol"] = clean_required_text(payload["symbol"]).upper()
    normalized["market"] = clean_required_text(payload.get("market", "TW")).upper()
    normalized["exchange"] = clean_required_text(payload["exchange"]).upper()
    normalized["board"] = clean_required_text(payload["board"]).lower()
    normalized["company_name"] = clean_required_text(payload["company_name"])
    normalized["trading_status"] = clean_required_text(
        payload["trading_status"]
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
    if normalized["market"] != "TW":
        raise ValueError("TW company profile market must be TW.")
    if normalized["trading_status"] != "active":
        raise ValueError("TW company profile trading_status must be active.")
    trusted_source = _SOURCE_BY_NAME.get(normalized["source_name"])
    if trusted_source is None:
        raise ValueError("TW company profile source_name is not trusted.")
    if (
        normalized["exchange"],
        normalized["board"],
    ) != (trusted_source.exchange, trusted_source.board):
        raise ValueError("TW company profile source pairing is invalid.")
    return normalized, trusted_source


def _verify_tw_company_profile_batch(
    payloads: list[dict],
) -> list[dict]:
    if not payloads:
        raise ValueError("TW company profile batch must not be empty.")
    normalized_profiles = [_normalize_company_profile(item) for item in payloads]
    first_payload, source = normalized_profiles[0]
    raw_record = _validate_company_profile_provenance(
        payload=first_payload,
        source=source,
    )
    raw_payload_id = first_payload["raw_payload_id"]
    archive_reference = first_payload["archive_object_reference"]
    for payload, item_source in normalized_profiles[1:]:
        if (
            item_source is not source
            or payload.get("raw_payload_id") != raw_payload_id
            or payload.get("archive_object_reference") != archive_reference
        ):
            raise ValueError("TW company profile batch provenance is inconsistent.")

    try:
        raw_records = _extract_record_list(json.loads(raw_record.payload_body))
    except (TypeError, ValueError):
        raw_records = None
    if raw_records is None:
        raise ValueError("TW company profile raw payload is invalid.")
    expected_fingerprints = set()
    for raw_item in raw_records:
        try:
            expected_payload = _build_profile_payload(
                item=raw_item,
                exchange=source.exchange,
                board=source.board,
                source_name=source.source_name,
                raw_payload_id=raw_payload_id,
                archive_reference=archive_reference,
            )
            normalized_expected, _ = _normalize_company_profile(expected_payload)
            expected_fingerprints.add(_profile_fingerprint(normalized_expected))
        except (KeyError, TypeError, ValueError):
            continue
    profile_fingerprints = frozenset(
        _profile_fingerprint(payload) for payload, _ in normalized_profiles
    )
    if not profile_fingerprints.issubset(expected_fingerprints):
        raise ValueError("TW company profile is not attested by its raw payload.")
    return [payload for payload, _ in normalized_profiles]


def save_tw_company_profiles(
    payloads: list[dict],
) -> list[CompanyProfileSaveOutcome]:
    try:
        normalized_profiles = _verify_tw_company_profile_batch(payloads)
    except Exception as exc:
        return [
            CompanyProfileSaveOutcome(payload=payload, saved=None, error=exc)
            for payload in payloads
        ]

    outcomes = []
    for payload in normalized_profiles:
        try:
            outcomes.append(
                CompanyProfileSaveOutcome(
                    payload=payload,
                    saved=upsert_tw_company_profile(payload),
                    error=None,
                )
            )
        except Exception as exc:
            outcomes.append(
                CompanyProfileSaveOutcome(
                    payload=payload,
                    saved=None,
                    error=exc,
                )
            )
    return outcomes


def save_tw_company_profile(payload: dict) -> dict:
    outcome = save_tw_company_profiles([payload])[0]
    if outcome.error is not None:
        raise outcome.error
    if outcome.saved is None:  # pragma: no cover - defensive invariant
        raise RuntimeError("TW company profile save produced no result.")
    return outcome.saved


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
