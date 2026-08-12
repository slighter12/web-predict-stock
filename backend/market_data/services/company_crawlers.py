from __future__ import annotations

import json
import logging
from typing import Any

import requests

from backend.market_data.repositories.company_profiles import (
    mark_missing_active_tw_company_profiles_inactive,
)
from backend.market_data.repositories.raw_ingest import (
    FETCH_STATUS_FAILED,
    FETCH_STATUS_SUCCESS,
    persist_raw_ingest_record,
)
from backend.market_data.services.company_profiles import (
    TPEX_COMPANY_SOURCE,
    TW_COMPANY_PARSER_VERSION,
    TW_COMPANY_SYMBOL,
    TWSE_COMPANY_SOURCE,
    CompanyProfileSource,
    _build_profile_payload,
    _extract_record_list,
    _first_value,
    count_active_tw_company_profiles,
    list_active_tw_company_profiles,
    save_tw_company_profiles,
)
from backend.market_data.services.tls_helpers import request_with_tls_fallback
from backend.platform.errors import (
    DataAccessError,
    ExternalFetchError,
    UnsupportedConfigurationError,
)
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)

TWSE_COMPANY_SOURCE_URL_DEFAULT = TWSE_COMPANY_SOURCE.url
TPEX_COMPANY_SOURCE_URL_DEFAULT = TPEX_COMPANY_SOURCE.url
TWSE_COMPANY_SOURCE_NAME = TWSE_COMPANY_SOURCE.source_name
TPEX_COMPANY_SOURCE_NAME = TPEX_COMPANY_SOURCE.source_name
_RECONCILIATION_MINIMUM_COVERAGE_RATIO = 0.95
_TRUSTED_COMPANY_SOURCES = (TWSE_COMPANY_SOURCE, TPEX_COMPANY_SOURCE)


def _describe_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = [str(key) for key in payload.keys()]
        return ",".join(keys[:10]) if keys else "<empty>"
    return type(payload).__name__


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


def _request_company_feed_with_tls_fallback(
    *, url: str, timeout_seconds: int
) -> requests.Response:
    return request_with_tls_fallback(
        method="GET",
        url=url,
        timeout_seconds=timeout_seconds,
        logger=logger,
        context_label="company feed fetch",
        allow_redirects=False,
    )


def _fetch_company_feed(
    *,
    source: CompanyProfileSource,
) -> tuple[int, list[dict[str, Any]]]:
    if not any(source is trusted for trusted in _TRUSTED_COMPANY_SOURCES):
        raise UnsupportedConfigurationError(
            "TW company feed source descriptor is not trusted."
        )
    url = source.url
    source_name = source.source_name
    payload_body = ""
    fetch_timestamp = utc_now()
    expected_context = f"source={source_name};market=TW"
    try:
        response = _request_company_feed_with_tls_fallback(
            url=url,
            timeout_seconds=30,
        )
        if response.url != source.url:
            raise UnsupportedConfigurationError(
                "TW company feed final URL does not match its trusted source."
            )
        if 300 <= response.status_code < 400:
            raise requests.exceptions.TooManyRedirects(
                "TW company feed redirect is not allowed."
            )
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException as exc:
        error_type = type(exc).__name__
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
        logger.warning(
            "TW company feed fetch failed source=%s error_type=%s",
            source_name,
            error_type,
        )
        raise ExternalFetchError(
            "Failed to fetch TW company feed.",
            error_type=error_type,
        ) from None

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
        selected[key]
        for key in sorted(selected.keys(), key=lambda item: (item[0], item[1]))
    ]
    return deduped_payloads, {
        "duplicate_symbol_count": duplicate_symbol_count,
        "conflict_count": conflict_count,
        "overwritten_count": overwritten_count,
    }


def _crawl_single_source(
    *,
    source: CompanyProfileSource,
    reconcile: bool = True,
) -> dict[str, Any]:
    source_name = source.source_name
    exchange = source.exchange
    board = source.board
    raw_payload_id, records = _fetch_company_feed(source=source)
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
                _first_value(
                    item,
                    "公司代號",
                    "股票代號",
                    "公司代碼",
                    "CompanyCode",
                )
                or "unknown"
            )
            errors.append(f"exchange={exchange} symbol={symbol}: {exc}")
    deduped_profiles, dedupe_summary = _dedupe_profile_payloads(built_profiles)
    existing_active_symbols = {
        str(record["symbol"]).strip().upper()
        for record in list_active_tw_company_profiles(limit=0)
        if str(record.get("exchange") or "").upper() == exchange
    } if records and reconcile else set()
    upserted_count = 0
    created_count = 0
    updated_count = 0
    noop_count = 0
    active_symbols: set[str] = set()
    save_outcomes = []
    if deduped_profiles:
        try:
            save_outcomes = save_tw_company_profiles(deduped_profiles)
        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning(
                "TW company profile batch save rejected exchange=%s "
                "raw_payload_id=%s error_type=%s",
                exchange,
                raw_payload_id,
                error_type,
            )
            errors.append(
                f"exchange={exchange} raw_payload_id={raw_payload_id} "
                f"batch_save_error_type={error_type}"
            )
    for outcome in save_outcomes:
        payload = outcome.payload
        if outcome.error is None and outcome.saved is not None:
            saved = outcome.saved
            active_symbols.add(saved["symbol"])
            upserted_count += 1
            write_action = saved.get("write_action")
            if write_action == "created":
                created_count += 1
            elif write_action == "updated":
                updated_count += 1
            else:
                noop_count += 1
        else:
            error_type = type(outcome.error).__name__
            errors.append(
                f"exchange={payload['exchange']} symbol={payload['symbol']} "
                f"save_error_type={error_type}"
            )
    inactivated_count = 0
    reconciliation_skipped = False
    if reconcile:
        reconciliation_skipped = True
    if reconcile and not records:
        errors.append(
            f"exchange={exchange} raw_payload_id={raw_payload_id} "
            "reconciliation skipped: company feed is empty."
        )
    elif reconcile and not errors:
        covered_symbol_count = len(active_symbols & existing_active_symbols)
        if (
            existing_active_symbols
            and covered_symbol_count
            < len(existing_active_symbols) * _RECONCILIATION_MINIMUM_COVERAGE_RATIO
        ):
            logger.warning(
                "Skipped TW company profile reconciliation due to low coverage "
                "exchange=%s existing_active_symbol_count=%s covered_symbol_count=%s",
                exchange,
                len(existing_active_symbols),
                covered_symbol_count,
            )
            errors.append(
                f"exchange={exchange} raw_payload_id={raw_payload_id} "
                "reconciliation skipped: "
                f"covered_symbol_count={covered_symbol_count} "
                f"existing_active_symbol_count={len(existing_active_symbols)}."
            )
        else:
            try:
                inactivated_count = mark_missing_active_tw_company_profiles_inactive(
                    exchange=exchange,
                    active_symbols=active_symbols,
                    source_name=source_name,
                    raw_payload_id=raw_payload_id,
                    archive_object_reference=archive_reference,
                )
                reconciliation_skipped = False
            except Exception as exc:
                error_type = type(exc).__name__
                logger.warning(
                    "TW company profile reconciliation failed exchange=%s "
                    "error_type=%s",
                    exchange,
                    error_type,
                    exc_info=True,
                )
                errors.append(
                    f"exchange={exchange} reconciliation error_type={error_type}"
                )
    return {
        "source_name": source_name,
        "exchange": exchange,
        "raw_payload_id": raw_payload_id,
        "processed_count": len(records),
        "upserted_count": upserted_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "noop_count": noop_count,
        "inactivated_count": inactivated_count,
        "reconciliation_requested": reconcile,
        "reconciliation_skipped": reconciliation_skipped,
        "duplicate_symbol_count": dedupe_summary["duplicate_symbol_count"],
        "conflict_count": dedupe_summary["conflict_count"],
        "overwritten_count": dedupe_summary["overwritten_count"],
        "errors": errors,
    }


def crawl_tw_company_profiles(
    *, include_tpex: bool = True, reconcile: bool = True
) -> dict[str, Any]:
    summaries = [
        _crawl_single_source(
            source=TWSE_COMPANY_SOURCE,
            reconcile=reconcile,
        )
    ]
    if include_tpex:
        summaries.append(
            _crawl_single_source(
                source=TPEX_COMPANY_SOURCE,
                reconcile=reconcile,
            )
        )

    return {
        "market": "TW",
        "source_names": [item["source_name"] for item in summaries],
        "source_summaries": summaries,
        "raw_payload_ids": [item["raw_payload_id"] for item in summaries],
        "processed_count": sum(item["processed_count"] for item in summaries),
        "upserted_count": sum(item["upserted_count"] for item in summaries),
        "created_count": sum(item["created_count"] for item in summaries),
        "updated_count": sum(item["updated_count"] for item in summaries),
        "noop_count": sum(item["noop_count"] for item in summaries),
        "inactivated_count": sum(item["inactivated_count"] for item in summaries),
        "reconciliation_requested": reconcile,
        "reconciliation_skipped": any(
            item["reconciliation_skipped"] for item in summaries
        ),
        "duplicate_symbol_count": sum(
            item["duplicate_symbol_count"] for item in summaries
        ),
        "conflict_count": sum(item["conflict_count"] for item in summaries),
        "overwritten_count": sum(item["overwritten_count"] for item in summaries),
        "active_symbol_count": count_active_tw_company_profiles(),
        "errors": [error for item in summaries for error in item["errors"]],
    }
