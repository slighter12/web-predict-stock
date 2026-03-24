from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import certifi
import requests

from backend.market_data.services import tls_helpers
from backend.platform.errors import ExternalFetchError

logger = logging.getLogger(__name__)

TWSE_PUBLIC_SNAPSHOT_SOURCE = "twse_public_snapshot"
TWSE_PUBLIC_SNAPSHOT_PARSER_VERSION = "twse_public_snapshot_parser_v1"
TWSE_PUBLIC_SNAPSHOT_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
_TW_TZ = ZoneInfo("Asia/Taipei")


_env_flag = tls_helpers.env_flag
_ca_bundle_target_path = tls_helpers.ca_bundle_target_path
_ca_bundle_download_url = tls_helpers.ca_bundle_download_url
_ca_auto_download_enabled = tls_helpers.ca_auto_download_enabled
_insecure_tls_fallback_enabled = tls_helpers.insecure_tls_fallback_enabled
_build_ssl_context = tls_helpers.build_ssl_context
_SSLContextAdapter = tls_helpers.SSLContextAdapter


def _download_ca_bundle() -> str:
    return tls_helpers.download_ca_bundle(
        download_url=_ca_bundle_download_url(),
        target_path=_ca_bundle_target_path(),
    )


def _resolve_tls_verify() -> bool | str:
    return tls_helpers.resolve_tls_verify(
        bundle_path=_ca_bundle_target_path(),
        skip_tls_verify=_env_flag("TWSE_MIS_SKIP_TLS_VERIFY"),
    )


def _request_snapshot(
    *,
    params: dict[str, str],
    timeout_seconds: int,
    verify: bool | str,
):
    if verify is False:
        return requests.get(
            TWSE_PUBLIC_SNAPSHOT_URL,
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout_seconds,
            verify=False,
        )

    ssl_context = _build_ssl_context(verify)
    session = requests.Session()
    session.mount("https://", _SSLContextAdapter(ssl_context))
    return session.get(
        TWSE_PUBLIC_SNAPSHOT_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout_seconds,
    )


def _split_field(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item for item in value.split("_") if item != ""]


def _to_float(value: str | None) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: str | None) -> int | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_observation_ts(
    payload: dict[str, Any], fetch_timestamp: datetime
) -> datetime:
    tlong = _to_int(str(payload.get("tlong")) if payload.get("tlong") else None)
    if tlong is not None and tlong > 0:
        return datetime.fromtimestamp(tlong / 1000, tz=timezone.utc)

    trading_date = str(payload.get("d") or payload.get("^") or "")
    trading_time = str(payload.get("t") or payload.get("%") or "")
    if len(trading_date) == 8 and trading_time:
        local_dt = datetime.strptime(
            f"{trading_date} {trading_time}",
            "%Y%m%d %H:%M:%S",
        ).replace(tzinfo=_TW_TZ)
        return local_dt.astimezone(timezone.utc)
    return fetch_timestamp


def parse_snapshot_payload(
    payload_body: str,
    *,
    fetch_timestamp: datetime,
) -> list[dict[str, Any]]:
    try:
        payload = json.loads(payload_body)
    except json.JSONDecodeError as exc:
        raise ValueError("TWSE public snapshot payload is not valid JSON.") from exc

    observations: list[dict[str, Any]] = []
    for item in payload.get("msgArray", []) or []:
        symbol = str(item.get("c") or "").strip()
        trading_date_raw = str(item.get("d") or item.get("^") or "").strip()
        if not symbol or len(trading_date_raw) != 8:
            continue
        try:
            trading_date = datetime.strptime(trading_date_raw, "%Y%m%d").date()
        except ValueError:
            continue

        observation_ts = _parse_observation_ts(item, fetch_timestamp)
        observations.append(
            {
                "trading_date": trading_date,
                "observation_ts": observation_ts,
                "symbol": symbol,
                "market": "TW",
                "last_price": _to_float(item.get("z")),
                "last_size": _to_int(item.get("tv")),
                "cumulative_volume": _to_int(item.get("v")),
                "best_bid_prices": [
                    value
                    for value in (_to_float(raw) for raw in _split_field(item.get("b")))
                    if value is not None
                ],
                "best_bid_sizes": [
                    value
                    for value in (_to_int(raw) for raw in _split_field(item.get("g")))
                    if value is not None
                ],
                "best_ask_prices": [
                    value
                    for value in (_to_float(raw) for raw in _split_field(item.get("a")))
                    if value is not None
                ],
                "best_ask_sizes": [
                    value
                    for value in (_to_int(raw) for raw in _split_field(item.get("f")))
                    if value is not None
                ],
                "source_name": TWSE_PUBLIC_SNAPSHOT_SOURCE,
                "parser_version": TWSE_PUBLIC_SNAPSHOT_PARSER_VERSION,
            }
        )
    return observations


def build_snapshot_request_symbols(symbols: list[str]) -> str:
    return "|".join(f"tse_{symbol}.tw" for symbol in symbols)


def fetch_twse_public_snapshot(
    symbols: list[str],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if not symbols:
        raise ValueError("At least one symbol is required for TWSE snapshot fetch.")

    ex_ch = build_snapshot_request_symbols(symbols)
    params = {"ex_ch": ex_ch, "json": "1", "delay": "0"}
    fetch_timestamp = datetime.now(timezone.utc)
    verify = _resolve_tls_verify()
    try:
        response = _request_snapshot(
            params=params,
            timeout_seconds=timeout_seconds,
            verify=verify,
        )
        response.raise_for_status()
    except requests.exceptions.SSLError:
        response = None
        if _ca_auto_download_enabled():
            try:
                downloaded_verify = _download_ca_bundle()
                response = _request_snapshot(
                    params=params,
                    timeout_seconds=timeout_seconds,
                    verify=downloaded_verify,
                )
                response.raise_for_status()
            except requests.RequestException:
                logger.exception(
                    "Failed to fetch TWSE public snapshot after CA download symbol_count=%s",
                    len(symbols),
                )
            except Exception:
                logger.exception(
                    "Failed to download TWSE MIS CA bundle symbol_count=%s",
                    len(symbols),
                )

        if response is None and _insecure_tls_fallback_enabled():
            logger.warning(
                "Retrying TWSE public snapshot without TLS verification symbol_count=%s",
                len(symbols),
            )
            try:
                response = _request_snapshot(
                    params=params,
                    timeout_seconds=timeout_seconds,
                    verify=False,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.exception(
                    "Failed to fetch TWSE public snapshot with insecure fallback symbol_count=%s",
                    len(symbols),
                )
                raise ExternalFetchError(
                    "Failed to fetch TWSE public snapshot."
                ) from exc

        if response is None:
            logger.exception(
                "TWSE public snapshot TLS verification failed symbol_count=%s auto_download=%s insecure_fallback=%s",
                len(symbols),
                _ca_auto_download_enabled(),
                _insecure_tls_fallback_enabled(),
            )
            raise ExternalFetchError("Failed to fetch TWSE public snapshot.") from None
    except requests.RequestException as exc:
        logger.exception(
            "Failed to fetch TWSE public snapshot symbol_count=%s", len(symbols)
        )
        raise ExternalFetchError("Failed to fetch TWSE public snapshot.") from exc

    payload_body = response.text
    observations = parse_snapshot_payload(
        payload_body,
        fetch_timestamp=fetch_timestamp,
    )
    return {
        "request_symbols": list(symbols),
        "fetch_timestamp": fetch_timestamp,
        "request_url": response.url,
        "response_status": response.status_code,
        "raw_response_body": payload_body,
        "observations": observations,
    }


def parse_archive_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    raw_response_body = str(entry.get("raw_response_body") or "")
    fetch_timestamp_value = entry.get("fetch_timestamp")
    if isinstance(fetch_timestamp_value, datetime):
        fetch_timestamp = fetch_timestamp_value.astimezone(timezone.utc)
    else:
        fetch_timestamp = datetime.fromisoformat(str(fetch_timestamp_value)).astimezone(
            timezone.utc
        )
    return parse_snapshot_payload(
        raw_response_body,
        fetch_timestamp=fetch_timestamp,
    )
