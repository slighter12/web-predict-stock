from __future__ import annotations

import json
import logging
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import certifi
import requests
from requests.adapters import HTTPAdapter

from backend.platform.errors import ExternalFetchError

logger = logging.getLogger(__name__)

TWSE_PUBLIC_SNAPSHOT_SOURCE = "twse_public_snapshot"
TWSE_PUBLIC_SNAPSHOT_PARSER_VERSION = "twse_public_snapshot_parser_v1"
TWSE_PUBLIC_SNAPSHOT_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
_TW_TZ = ZoneInfo("Asia/Taipei")
_DEFAULT_CA_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "var" / "certs" / "twse-mis-ca.pem"
)


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _ca_bundle_target_path() -> Path:
    raw_path = (os.getenv("TWSE_MIS_CA_BUNDLE") or "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    raw_cache_path = (os.getenv("TWSE_MIS_CA_CACHE_PATH") or "").strip()
    if raw_cache_path:
        return Path(raw_cache_path).expanduser()
    return _DEFAULT_CA_CACHE_PATH


def _ca_bundle_download_url() -> str | None:
    raw_url = (os.getenv("TWSE_MIS_CA_BUNDLE_URL") or "").strip()
    return raw_url or None


def _ca_auto_download_enabled() -> bool:
    return _env_flag("TWSE_MIS_CA_AUTO_DOWNLOAD")


def _insecure_tls_fallback_enabled() -> bool:
    return _env_flag("TWSE_MIS_ENABLE_INSECURE_FALLBACK")


def _download_ca_bundle() -> str:
    download_url = _ca_bundle_download_url()
    if not download_url:
        raise ValueError("TWSE MIS CA bundle URL is not configured.")

    target_path = _ca_bundle_target_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        download_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return str(target_path)


def _resolve_tls_verify() -> bool | str:
    ca_bundle_path = _ca_bundle_target_path()
    if ca_bundle_path.exists():
        return str(ca_bundle_path)
    if _env_flag("TWSE_MIS_SKIP_TLS_VERIFY"):
        return False
    return certifi.where()


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


def _build_ssl_context(verify: bool | str) -> ssl.SSLContext:
    if verify is True:
        context = ssl.create_default_context()
    else:
        context = ssl.create_default_context(cafile=str(verify))
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


class _SSLContextAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs: Any) -> None:
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            **pool_kwargs,
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
                raise ExternalFetchError("Failed to fetch TWSE public snapshot.") from exc

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
