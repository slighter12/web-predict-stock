import logging

import pytest
import requests

import backend.market_data.services.tls_helpers as tls_helpers


def test_tls_fallback_logs_do_not_expose_request_url(caplog, monkeypatch):
    secret_url = "https://feed.test/data?token=secret"
    outcomes = iter(
        [
            requests.exceptions.SSLError(f"TLS failed for {secret_url}"),
            requests.exceptions.HTTPError(f"Forbidden for url: {secret_url}"),
        ]
    )

    def fake_request(**kwargs):
        outcome = next(outcomes)
        raise outcome

    monkeypatch.setattr(tls_helpers, "resolve_tls_verify", lambda: "default.pem")
    monkeypatch.setattr(tls_helpers, "perform_tls_request", fake_request)
    monkeypatch.setattr(tls_helpers, "ca_auto_download_enabled", lambda: True)
    monkeypatch.setattr(tls_helpers, "download_ca_bundle", lambda: "downloaded.pem")
    monkeypatch.setattr(tls_helpers, "insecure_tls_fallback_enabled", lambda: False)
    caplog.set_level(logging.ERROR)

    with pytest.raises(requests.exceptions.SSLError):
        tls_helpers.request_with_tls_fallback(
            method="GET",
            url=secret_url,
            timeout_seconds=30,
            logger=logging.getLogger("test_tls_fallback"),
            context_label="company feed fetch",
        )

    assert "HTTPError" in caplog.text
    assert "token=secret" not in caplog.text
