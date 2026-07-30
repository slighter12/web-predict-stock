from __future__ import annotations

import traceback
from datetime import datetime, timezone

import pytest
import requests

import backend.market_data.services.official_crawlers as official_event_crawler_service
from backend.platform.errors import ExternalFetchError


def test_crawl_lifecycle_records_links_raw_payload(monkeypatch):
    captured_requests: list[object] = []

    monkeypatch.setattr(
        official_event_crawler_service,
        "_fetch_official_feed",
        lambda url_env, source_name: (
            51,
            [
                {
                    "symbol": "2330",
                    "market": "TW",
                    "event_type": "listing",
                    "effective_date": "2000-01-01",
                }
            ],
        ),
    )
    monkeypatch.setattr(
        official_event_crawler_service,
        "save_lifecycle_record",
        lambda request: captured_requests.append(request) or {"id": 1},
    )

    summary = official_event_crawler_service.crawl_lifecycle_records()

    assert summary["processed_count"] == 1
    assert summary["upserted_count"] == 1
    assert captured_requests[0].raw_payload_id == 51
    assert captured_requests[0].archive_object_reference == "raw_ingest_audit:51"


def test_crawl_important_events_links_raw_payload(monkeypatch):
    captured_requests: list[object] = []

    monkeypatch.setattr(
        official_event_crawler_service,
        "_fetch_official_feed",
        lambda url_env, source_name: (
            61,
            [
                {
                    "symbol": "2330",
                    "market": "TW",
                    "event_type": "cash_dividend",
                    "effective_date": "2026-03-20",
                    "event_publication_ts": "2026-03-19T00:00:00+00:00",
                    "timestamp_source_class": "official_exchange",
                }
            ],
        ),
    )
    monkeypatch.setattr(
        official_event_crawler_service,
        "save_important_event",
        lambda request: captured_requests.append(request) or {"id": 1},
    )

    summary = official_event_crawler_service.crawl_important_events()

    assert summary["processed_count"] == 1
    assert summary["upserted_count"] == 1
    assert captured_requests[0].raw_payload_id == 61
    assert captured_requests[0].event_publication_ts == datetime(
        2026, 3, 19, tzinfo=timezone.utc
    )


def test_official_feed_failure_does_not_expose_request_url(
    caplog,
    monkeypatch,
):
    secret_url = "https://feed.test/events?token=secret"
    monkeypatch.setenv(
        official_event_crawler_service.LIFECYCLE_SOURCE_URL_ENV,
        secret_url,
    )
    monkeypatch.setattr(
        official_event_crawler_service.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            requests.HTTPError(f"Forbidden for url: {secret_url}")
        ),
    )
    monkeypatch.setattr(
        official_event_crawler_service,
        "persist_raw_ingest_record",
        lambda **kwargs: 1,
    )

    with pytest.raises(ExternalFetchError) as exc_info:
        official_event_crawler_service._fetch_official_feed(
            official_event_crawler_service.LIFECYCLE_SOURCE_URL_ENV,
            official_event_crawler_service.LIFECYCLE_SOURCE_NAME,
        )

    assert str(exc_info.value) == "Failed to fetch official feed."
    assert exc_info.value.error_type == "HTTPError"
    assert "token=secret" not in "".join(
        traceback.format_exception(exc_info.value)
    )
    assert "token=secret" not in caplog.text
