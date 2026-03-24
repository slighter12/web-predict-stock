from __future__ import annotations

import logging
import os
import ssl
from pathlib import Path
from typing import Any

import certifi
import requests
from requests.adapters import HTTPAdapter

_DEFAULT_CA_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "var" / "certs" / "twse-mis-ca.pem"
)


def env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def ca_bundle_target_path() -> Path:
    raw_path = (os.getenv("TWSE_MIS_CA_BUNDLE") or "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    raw_cache_path = (os.getenv("TWSE_MIS_CA_CACHE_PATH") or "").strip()
    if raw_cache_path:
        return Path(raw_cache_path).expanduser()
    return _DEFAULT_CA_CACHE_PATH


def ca_bundle_download_url() -> str | None:
    raw_url = (os.getenv("TWSE_MIS_CA_BUNDLE_URL") or "").strip()
    return raw_url or None


def ca_auto_download_enabled() -> bool:
    return env_flag("TWSE_MIS_CA_AUTO_DOWNLOAD")


def insecure_tls_fallback_enabled() -> bool:
    return env_flag("TWSE_MIS_ENABLE_INSECURE_FALLBACK")


def download_ca_bundle(
    *,
    download_url: str | None = None,
    target_path: Path | None = None,
) -> str:
    download_url = download_url or ca_bundle_download_url()
    if not download_url:
        raise ValueError("TWSE MIS CA bundle URL is not configured.")

    target_path = target_path or ca_bundle_target_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        download_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return str(target_path)


def resolve_tls_verify(
    *,
    bundle_path: Path | None = None,
    skip_tls_verify: bool | None = None,
) -> bool | str:
    bundle_path = bundle_path or ca_bundle_target_path()
    if bundle_path.exists():
        return str(bundle_path)
    if skip_tls_verify is None:
        skip_tls_verify = env_flag("TWSE_MIS_SKIP_TLS_VERIFY")
    if skip_tls_verify:
        return False
    return certifi.where()


def build_ssl_context(verify: bool | str) -> ssl.SSLContext:
    if verify is True:
        context = ssl.create_default_context()
    else:
        context = ssl.create_default_context(cafile=str(verify))
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


class SSLContextAdapter(HTTPAdapter):
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


def perform_tls_request(
    *,
    method: str,
    url: str,
    timeout_seconds: int,
    verify: bool | str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
) -> requests.Response:
    request_kwargs = {"timeout": timeout_seconds}
    if headers is not None:
        request_kwargs["headers"] = headers
    if params is not None:
        request_kwargs["params"] = params
    if data is not None:
        request_kwargs["data"] = data
    if verify is False:
        return requests.request(method, url, verify=False, **request_kwargs)

    session = requests.Session()
    session.mount("https://", SSLContextAdapter(build_ssl_context(verify)))
    return session.request(method, url, **request_kwargs)


def request_with_tls_fallback(
    *,
    method: str,
    url: str,
    timeout_seconds: int,
    logger: logging.Logger,
    context_label: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
) -> requests.Response:
    verify = resolve_tls_verify()
    try:
        return perform_tls_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            timeout_seconds=timeout_seconds,
            verify=verify,
        )
    except requests.exceptions.SSLError:
        response = None
        if ca_auto_download_enabled():
            try:
                downloaded_verify = download_ca_bundle()
                response = perform_tls_request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    timeout_seconds=timeout_seconds,
                    verify=downloaded_verify,
                )
            except requests.RequestException:
                logger.exception(
                    "Failed %s after CA download url=%s",
                    context_label,
                    url,
                )
            except Exception:
                logger.exception(
                    "Failed to download CA bundle for %s url=%s",
                    context_label,
                    url,
                )

        if response is None and insecure_tls_fallback_enabled():
            logger.warning(
                "Retrying %s without TLS verification url=%s",
                context_label,
                url,
            )
            response = perform_tls_request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                timeout_seconds=timeout_seconds,
                verify=False,
            )

        if response is None:
            raise
        return response
