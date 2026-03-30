from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

import backend.market_data.services.tick_archive_provider as tick_archive_provider
import backend.market_data.services.tick_archives as tick_archive_service
import backend.market_data.services.tick_governance as tick_gate_service
import backend.market_data.services.tick_ops as tick_ops_kpi_service
import backend.market_data.services.tick_replay as tick_replay_service
from backend.platform.errors import DataNotFoundError, ExternalFetchError


def test_parse_snapshot_payload_extracts_tick_observations():
    payload_body = """
    {
      "msgArray": [
        {
          "c": "2330",
          "d": "20260320",
          "tlong": "1773988200000",
          "z": "1840.0000",
          "tv": "24094",
          "v": "46139",
          "a": "1845.0000_1850.0000_",
          "f": "110_496_",
          "b": "1840.0000_1835.0000_",
          "g": "763_2726_"
        }
      ]
    }
    """

    observations = tick_archive_provider.parse_snapshot_payload(
        payload_body,
        fetch_timestamp=datetime(2026, 3, 20, 7, 35, tzinfo=timezone.utc),
    )

    assert len(observations) == 1
    assert observations[0]["symbol"] == "2330"
    assert observations[0]["market"] == "TW"
    assert observations[0]["last_price"] == 1840.0
    assert observations[0]["last_size"] == 24094
    assert observations[0]["best_bid_prices"] == [1840.0, 1835.0]
    assert observations[0]["best_ask_sizes"] == [110, 496]


def test_fetch_twse_public_snapshot_prefers_ca_bundle(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type(
            "P",
            (),
            {"exists": lambda self: True, "__str__": lambda self: "/tmp/twse-ca.pem"},
        )(),
    )

    monkeypatch.setenv("TWSE_MIS_CA_BUNDLE", "/tmp/twse-ca.pem")
    monkeypatch.delenv("TWSE_MIS_SKIP_TLS_VERIFY", raising=False)
    monkeypatch.setattr(
        tick_archive_provider,
        "_build_ssl_context",
        lambda verify: captured.setdefault("verify", verify) or SimpleNamespace(),
    )

    class FakeSession:
        def mount(self, prefix, adapter):
            captured["mounted"] = prefix

        def get(self, url, *, params, headers, timeout):
            return SimpleNamespace(
                status_code=200,
                url="https://mis.twse.com.tw/mock",
                text='{"msgArray":[]}',
                raise_for_status=lambda: None,
            )

    monkeypatch.setattr(tick_archive_provider.requests, "Session", FakeSession)

    tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert captured["verify"] == "/tmp/twse-ca.pem"


def test_fetch_twse_public_snapshot_can_skip_tls_verify(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type("P", (), {"exists": lambda self: False})(),
    )

    def fake_get(url, *, params, headers, timeout, verify):
        captured["verify"] = verify
        return SimpleNamespace(
            status_code=200,
            url="https://mis.twse.com.tw/mock",
            text='{"msgArray":[]}',
            raise_for_status=lambda: None,
        )

    monkeypatch.delenv("TWSE_MIS_CA_BUNDLE", raising=False)
    monkeypatch.setenv("TWSE_MIS_SKIP_TLS_VERIFY", "true")
    monkeypatch.setattr(tick_archive_provider.requests, "get", fake_get)

    tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert captured["verify"] is False


def test_fetch_twse_public_snapshot_defaults_to_certifi_bundle(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type("P", (), {"exists": lambda self: False})(),
    )

    monkeypatch.delenv("TWSE_MIS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("TWSE_MIS_CA_CACHE_PATH", raising=False)
    monkeypatch.delenv("TWSE_MIS_SKIP_TLS_VERIFY", raising=False)
    monkeypatch.setattr(
        tick_archive_provider,
        "_build_ssl_context",
        lambda verify: captured.setdefault("verify", verify) or SimpleNamespace(),
    )

    class FakeSession:
        def mount(self, prefix, adapter):
            captured["mounted"] = prefix

        def get(self, url, *, params, headers, timeout):
            return SimpleNamespace(
                status_code=200,
                url="https://mis.twse.com.tw/mock",
                text='{"msgArray":[]}',
                raise_for_status=lambda: None,
            )

    monkeypatch.setattr(tick_archive_provider.requests, "Session", FakeSession)

    tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert captured["verify"] == tick_archive_provider.certifi.where()


def test_fetch_twse_public_snapshot_auto_downloads_ca_on_tls_failure(monkeypatch):
    captured: list = []
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type("P", (), {"exists": lambda self: False})(),
    )

    def fake_request_snapshot(*, params, timeout_seconds, verify):
        captured.append(verify)
        if len(captured) == 1:
            raise tick_archive_provider.requests.exceptions.SSLError("bad cert")
        return SimpleNamespace(
            status_code=200,
            url="https://mis.twse.com.tw/mock",
            text='{"msgArray":[]}',
            raise_for_status=lambda: None,
        )

    monkeypatch.setenv("TWSE_MIS_CA_AUTO_DOWNLOAD", "true")
    monkeypatch.setenv("TWSE_MIS_CA_BUNDLE_URL", "https://example.com/twse-ca.pem")
    monkeypatch.delenv("TWSE_MIS_SKIP_TLS_VERIFY", raising=False)
    monkeypatch.setattr(
        tick_archive_provider,
        "_request_snapshot",
        fake_request_snapshot,
    )
    monkeypatch.setattr(
        tick_archive_provider,
        "_download_ca_bundle",
        lambda: "/tmp/downloaded-ca.pem",
    )

    tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert captured == [
        tick_archive_provider.certifi.where(),
        "/tmp/downloaded-ca.pem",
    ]


def test_fetch_twse_public_snapshot_insecure_fallback_requires_explicit_opt_in(
    monkeypatch,
):
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type("P", (), {"exists": lambda self: False})(),
    )

    calls: list[bool | str] = []

    def fake_request_snapshot(*, params, timeout_seconds, verify):
        calls.append(verify)
        raise tick_archive_provider.requests.exceptions.SSLError("bad cert")

    monkeypatch.delenv("TWSE_MIS_SKIP_TLS_VERIFY", raising=False)
    monkeypatch.delenv("TWSE_MIS_CA_AUTO_DOWNLOAD", raising=False)
    monkeypatch.delenv("TWSE_MIS_ENABLE_INSECURE_FALLBACK", raising=False)
    monkeypatch.setattr(
        tick_archive_provider,
        "_request_snapshot",
        fake_request_snapshot,
    )

    with pytest.raises(
        ExternalFetchError, match="Failed to fetch TWSE public snapshot."
    ):
        tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert calls == [tick_archive_provider.certifi.where()]


def test_fetch_twse_public_snapshot_can_use_explicit_insecure_fallback(monkeypatch):
    calls: list[bool | str] = []
    monkeypatch.setattr(
        tick_archive_provider,
        "_ca_bundle_target_path",
        lambda: type("P", (), {"exists": lambda self: False})(),
    )

    def fake_request_snapshot(*, params, timeout_seconds, verify):
        calls.append(verify)
        if len(calls) == 1:
            raise tick_archive_provider.requests.exceptions.SSLError("bad cert")
        return SimpleNamespace(
            status_code=200,
            url="https://mis.twse.com.tw/mock",
            text='{"msgArray":[]}',
            raise_for_status=lambda: None,
        )

    monkeypatch.delenv("TWSE_MIS_SKIP_TLS_VERIFY", raising=False)
    monkeypatch.delenv("TWSE_MIS_CA_AUTO_DOWNLOAD", raising=False)
    monkeypatch.setenv("TWSE_MIS_ENABLE_INSECURE_FALLBACK", "true")
    monkeypatch.setattr(
        tick_archive_provider,
        "_request_snapshot",
        fake_request_snapshot,
    )

    tick_archive_provider.fetch_twse_public_snapshot(["2330"])

    assert calls == [tick_archive_provider.certifi.where(), False]


def test_create_tick_archive_dispatch_persists_run_and_objects(monkeypatch):
    persisted_runs: list[dict] = []
    persisted_objects: list[dict] = []
    normalized_writes: list[dict] = []

    def capture_run(payload):
        record = {"id": payload.get("id", len(persisted_runs) + 1), **payload}
        persisted_runs.append(record)
        return record

    monkeypatch.setattr(
        tick_archive_service,
        "persist_tick_archive_run",
        capture_run,
    )
    monkeypatch.setattr(
        tick_archive_service,
        "resolve_tw_tick_archive_symbols",
        lambda *, trading_date: ["2330", "2317"],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "fetch_twse_public_snapshot",
        lambda symbols: {
            "request_symbols": symbols,
            "fetch_timestamp": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
            "request_url": "https://mis.twse.com.tw/mock",
            "response_status": 200,
            "raw_response_body": '{"msgArray":[]}',
            "observations": [
                {
                    "trading_date": date(2026, 3, 20),
                    "observation_ts": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
                    "symbol": "2330",
                    "market": "TW",
                    "last_price": 1840.0,
                    "last_size": 24094,
                    "cumulative_volume": 46139,
                    "best_bid_prices": [1840.0],
                    "best_bid_sizes": [763],
                    "best_ask_prices": [1845.0],
                    "best_ask_sizes": [110],
                    "source_name": "twse_public_snapshot",
                    "parser_version": "twse_public_snapshot_parser_v1",
                }
            ],
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_archive_part",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
            "compressed_bytes": 128,
            "uncompressed_bytes": 512,
            "compression_ratio": 0.75,
            "checksum": "abc123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_normalized_archive_part",
        lambda **kwargs: (
            normalized_writes.append(kwargs)
            or {
                "object_key": "var/tick_archives/TW/2026-03-20/1/normalized/part-00001.jsonl.gz",
                "compressed_bytes": 96,
                "uncompressed_bytes": 256,
                "compression_ratio": 0.625,
                "checksum": "normalized123",
            }
        ),
    )
    monkeypatch.setattr(
        tick_archive_service,
        "persist_tick_archive_object",
        lambda payload: persisted_objects.append(payload) or {"id": 1, **payload},
    )

    request = type(
        "TickDispatchRequest",
        (),
        {
            "market": "TW",
            "trading_date": date(2026, 3, 20),
            "mode": "post_close_crawl",
            "notes": "manual dispatch",
        },
    )()

    result = tick_archive_service.create_tick_archive_dispatch(request)

    assert result["status"] == "succeeded"
    assert result["symbol_count"] == 2
    assert result["request_count"] == 1
    assert result["observation_count"] == 1
    assert persisted_objects[0]["record_count"] == 1
    assert len(normalized_writes) == 1


def test_create_tick_archive_dispatch_raises_after_persisting_failed_run(monkeypatch):
    persisted_runs: list[dict] = []

    def capture_run(payload):
        record = {"id": payload.get("id", len(persisted_runs) + 1), **payload}
        persisted_runs.append(record)
        return record

    monkeypatch.setattr(tick_archive_service, "persist_tick_archive_run", capture_run)
    monkeypatch.setattr(
        tick_archive_service,
        "resolve_tw_tick_archive_symbols",
        lambda *, trading_date: ["2330"],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "fetch_twse_public_snapshot",
        lambda symbols: (_ for _ in ()).throw(
            ExternalFetchError("upstream snapshot unavailable")
        ),
    )

    request = type(
        "TickDispatchRequest",
        (),
        {
            "market": "TW",
            "trading_date": date(2026, 3, 20),
            "mode": "post_close_crawl",
            "notes": "dispatch failure",
        },
    )()

    with pytest.raises(ExternalFetchError, match="upstream snapshot unavailable"):
        tick_archive_service.create_tick_archive_dispatch(request)

    assert persisted_runs[-1]["status"] == "failed"
    assert "upstream snapshot unavailable" in str(persisted_runs[-1]["abort_reason"])


def test_create_tick_archive_dispatch_cleans_up_persisted_parts_on_late_failure(
    monkeypatch,
):
    persisted_runs: list[dict] = []
    persisted_objects: list[dict] = []
    deleted_object_ids: list[int] = []
    deleted_keys: list[str] = []

    def capture_run(payload):
        record = {"id": payload.get("id", len(persisted_runs) + 1), **payload}
        persisted_runs.append(record)
        return record

    def capture_object(payload):
        record = {"id": len(persisted_objects) + 1, **payload}
        persisted_objects.append(record)
        return record

    fetch_results = iter(
        [
            {
                "request_symbols": ["2330"],
                "fetch_timestamp": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
                "request_url": "https://mis.twse.com.tw/mock/1",
                "response_status": 200,
                "raw_response_body": '{"msgArray":[]}',
                "observations": [
                    {
                        "trading_date": date(2026, 3, 20),
                        "observation_ts": datetime(
                            2026, 3, 20, 7, 5, tzinfo=timezone.utc
                        ),
                        "symbol": "2330",
                        "market": "TW",
                        "last_price": 1840.0,
                        "last_size": 24094,
                        "cumulative_volume": 46139,
                        "best_bid_prices": [1840.0],
                        "best_bid_sizes": [763],
                        "best_ask_prices": [1845.0],
                        "best_ask_sizes": [110],
                        "source_name": "twse_public_snapshot",
                        "parser_version": "twse_public_snapshot_parser_v1",
                    }
                ],
            },
            ExternalFetchError("late-part failure"),
        ]
    )

    def fake_fetch(symbols):
        next_item = next(fetch_results)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item

    write_results = iter(
        [
            {
                "object_key": "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
                "compressed_bytes": 128,
                "uncompressed_bytes": 512,
                "compression_ratio": 0.75,
                "checksum": "abc123",
            }
        ]
    )

    monkeypatch.setattr(tick_archive_service, "persist_tick_archive_run", capture_run)
    monkeypatch.setattr(
        tick_archive_service,
        "resolve_tw_tick_archive_symbols",
        lambda *, trading_date: ["2330", "2317"],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "_chunk_symbols",
        lambda symbols, chunk_size: [["2330"], ["2317"]],
    )
    monkeypatch.setattr(tick_archive_service, "fetch_twse_public_snapshot", fake_fetch)
    monkeypatch.setattr(
        tick_archive_service, "write_archive_part", lambda **kwargs: next(write_results)
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_normalized_archive_part",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-20/1/normalized/part-00001.jsonl.gz",
            "compressed_bytes": 96,
            "uncompressed_bytes": 256,
            "compression_ratio": 0.625,
            "checksum": "normalized123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service, "persist_tick_archive_object", capture_object
    )
    monkeypatch.setattr(
        tick_archive_service,
        "delete_tick_archive_objects",
        lambda object_ids: deleted_object_ids.extend(object_ids) or len(object_ids),
    )
    monkeypatch.setattr(
        tick_archive_service,
        "delete_archive_object",
        lambda *, object_key, storage_backend: deleted_keys.append(object_key) or True,
    )

    request = type(
        "TickDispatchRequest",
        (),
        {
            "market": "TW",
            "trading_date": date(2026, 3, 20),
            "mode": "post_close_crawl",
            "notes": "late failure cleanup",
        },
    )()

    with pytest.raises(ExternalFetchError, match="late-part failure"):
        tick_archive_service.create_tick_archive_dispatch(request)

    assert deleted_object_ids == [1]
    assert deleted_keys == [
        "var/tick_archives/TW/2026-03-20/1/normalized/part-00001.jsonl.gz",
        "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
    ]
    assert persisted_runs[-1]["status"] == "failed"
    assert persisted_runs[-1]["observation_count"] == 0


def test_create_tick_archive_dispatch_resolves_symbols_for_requested_trading_date(
    monkeypatch,
):
    captured_trading_dates: list[date] = []

    def capture_run(payload):
        return {"id": payload.get("id", 1), **payload}

    monkeypatch.setattr(tick_archive_service, "persist_tick_archive_run", capture_run)
    monkeypatch.setattr(
        tick_archive_service,
        "resolve_tw_tick_archive_symbols",
        lambda *, trading_date: captured_trading_dates.append(trading_date) or ["2330"],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "fetch_twse_public_snapshot",
        lambda symbols: {
            "request_symbols": symbols,
            "fetch_timestamp": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
            "request_url": "https://mis.twse.com.tw/mock",
            "response_status": 200,
            "raw_response_body": '{"msgArray":[]}',
            "observations": [
                {
                    "trading_date": date(2026, 3, 18),
                    "observation_ts": datetime(2026, 3, 18, 7, 5, tzinfo=timezone.utc),
                    "symbol": "2330",
                    "market": "TW",
                    "last_price": 1840.0,
                    "last_size": 24094,
                    "cumulative_volume": 46139,
                    "best_bid_prices": [1840.0],
                    "best_bid_sizes": [763],
                    "best_ask_prices": [1845.0],
                    "best_ask_sizes": [110],
                    "source_name": "twse_public_snapshot",
                    "parser_version": "twse_public_snapshot_parser_v1",
                }
            ],
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_archive_part",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-18/1/part-00001.jsonl.gz",
            "compressed_bytes": 128,
            "uncompressed_bytes": 512,
            "compression_ratio": 0.75,
            "checksum": "abc123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_normalized_archive_part",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-18/1/normalized/part-00001.jsonl.gz",
            "compressed_bytes": 96,
            "uncompressed_bytes": 256,
            "compression_ratio": 0.625,
            "checksum": "normalized123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "persist_tick_archive_object",
        lambda payload: {"id": 1, **payload},
    )

    request = type(
        "TickDispatchRequest",
        (),
        {
            "market": "TW",
            "trading_date": date(2026, 3, 18),
            "mode": "post_close_crawl",
            "notes": "historical dispatch",
        },
    )()

    tick_archive_service.create_tick_archive_dispatch(request)

    assert captured_trading_dates == [date(2026, 3, 18)]


def test_create_tick_archive_import_rejects_mismatched_archive_metadata(monkeypatch):
    persisted_runs: list[dict] = []
    deleted_keys: list[str] = []

    def capture_run(payload):
        record = {"id": payload.get("id", len(persisted_runs) + 1), **payload}
        persisted_runs.append(record)
        return record

    monkeypatch.setattr(tick_archive_service, "persist_tick_archive_run", capture_run)
    monkeypatch.setattr(
        tick_archive_service,
        "write_uploaded_archive",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-21/1/upload.jsonl.gz",
            "compressed_bytes": 128,
            "uncompressed_bytes": 512,
            "compression_ratio": 0.75,
            "checksum": "abc123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "read_archive_entries",
        lambda object_key: [
            {
                "raw_response_body": '{"msgArray":[]}',
                "fetch_timestamp": "2026-03-20T07:05:00+00:00",
                "request_symbols": ["2330"],
            }
        ],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "parse_archive_entry",
        lambda entry: [
            {
                "trading_date": date(2026, 3, 20),
                "observation_ts": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
                "symbol": "2330",
                "market": "TW",
                "last_price": 1840.0,
                "last_size": 24094,
                "cumulative_volume": 46139,
                "best_bid_prices": [1840.0],
                "best_bid_sizes": [763],
                "best_ask_prices": [1845.0],
                "best_ask_sizes": [110],
                "source_name": "twse_public_snapshot",
                "parser_version": "twse_public_snapshot_parser_v1",
            }
        ],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "delete_archive_object",
        lambda *, object_key, storage_backend: deleted_keys.append(object_key) or True,
    )

    with pytest.raises(
        ValueError, match="trading_date does not match archive observations"
    ):
        tick_archive_service.create_tick_archive_import(
            market="TW",
            trading_date=date(2026, 3, 21),
            notes="metadata mismatch",
            file_bytes=b"gzip-content",
        )

    assert persisted_runs[-1]["status"] == "failed"
    assert deleted_keys == ["var/tick_archives/TW/2026-03-21/1/upload.jsonl.gz"]


def test_create_tick_archive_import_writes_normalized_sidecar(monkeypatch):
    persisted_runs: list[dict] = []
    persisted_objects: list[dict] = []
    normalized_writes: list[dict] = []

    def capture_run(payload):
        record = {"id": payload.get("id", len(persisted_runs) + 1), **payload}
        persisted_runs.append(record)
        return record

    monkeypatch.setattr(tick_archive_service, "persist_tick_archive_run", capture_run)
    monkeypatch.setattr(
        tick_archive_service,
        "write_uploaded_archive",
        lambda **kwargs: {
            "object_key": "var/tick_archives/TW/2026-03-21/1/part-00001.jsonl.gz",
            "compressed_bytes": 128,
            "uncompressed_bytes": 512,
            "compression_ratio": 0.75,
            "checksum": "abc123",
        },
    )
    monkeypatch.setattr(
        tick_archive_service,
        "read_archive_entries",
        lambda object_key: [
            {
                "raw_response_body": '{"msgArray":[]}',
                "fetch_timestamp": "2026-03-21T02:05:00+00:00",
                "request_symbols": ["2330"],
            }
        ],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "parse_archive_entry",
        lambda entry: [
            {
                "trading_date": date(2026, 3, 21),
                "observation_ts": datetime(2026, 3, 21, 2, 5, tzinfo=timezone.utc),
                "symbol": "2330",
                "market": "TW",
                "last_price": 1840.0,
                "last_size": 24094,
                "cumulative_volume": 46139,
                "best_bid_prices": [1840.0],
                "best_bid_sizes": [763],
                "best_ask_prices": [1845.0],
                "best_ask_sizes": [110],
                "source_name": "twse_public_snapshot",
                "parser_version": "twse_public_snapshot_parser_v1",
            }
        ],
    )
    monkeypatch.setattr(
        tick_archive_service,
        "write_normalized_archive_part",
        lambda **kwargs: (
            normalized_writes.append(kwargs)
            or {
                "object_key": "var/tick_archives/TW/2026-03-21/1/normalized/part-00001.jsonl.gz",
                "compressed_bytes": 96,
                "uncompressed_bytes": 256,
                "compression_ratio": 0.625,
                "checksum": "normalized123",
            }
        ),
    )
    monkeypatch.setattr(
        tick_archive_service,
        "persist_tick_archive_object",
        lambda payload: persisted_objects.append(payload) or {"id": 1, **payload},
    )
    monkeypatch.setattr(
        tick_archive_service,
        "_collect_backup_metadata",
        lambda object_key: {
            "backup_backend": "google_drive_mirror",
            "backup_object_key": None,
            "backup_status": "not_configured",
            "backup_completed_at": None,
            "backup_error": None,
        },
    )

    result = tick_archive_service.create_tick_archive_import(
        market="TW",
        trading_date=date(2026, 3, 21),
        notes="manual import",
        file_bytes=b"gzip-content",
    )

    assert result["run"]["status"] == "succeeded"
    assert result["archive_object"]["record_count"] == 1
    assert len(normalized_writes) == 1
    assert normalized_writes[0]["part_number"] == 1
    assert persisted_objects[0]["object_key"] == (
        "var/tick_archives/TW/2026-03-21/1/part-00001.jsonl.gz"
    )


def test_create_tick_replay_persists_restore_metrics(monkeypatch):
    persisted_payloads: list[dict] = []
    monkeypatch.setattr(
        tick_replay_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: None,
    )
    monkeypatch.setattr(
        tick_replay_service,
        "get_tick_archive_object",
        lambda archive_object_id: {
            "id": archive_object_id,
            "object_key": "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
            "compressed_bytes": 1024 * 1024,
        },
    )
    monkeypatch.setattr(
        tick_replay_service,
        "read_archive_entries",
        lambda object_key: [
            {"raw_response_body": "{}", "fetch_timestamp": "2026-03-20T07:05:00+00:00"}
        ],
    )
    monkeypatch.setattr(
        tick_replay_service,
        "parse_archive_entry",
        lambda entry: [
            {
                "trading_date": date(2026, 3, 20),
                "observation_ts": datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc),
                "symbol": "2330",
                "market": "TW",
                "last_price": 1840.0,
                "last_size": 24094,
                "cumulative_volume": 46139,
                "best_bid_prices": [1840.0],
                "best_bid_sizes": [763],
                "best_ask_prices": [1845.0],
                "best_ask_sizes": [110],
                "source_name": "twse_public_snapshot",
                "parser_version": "twse_public_snapshot_parser_v1",
            }
        ],
    )
    monkeypatch.setattr(
        tick_replay_service,
        "replace_tick_observations",
        lambda archive_object_reference, observations: len(observations),
    )
    monkeypatch.setattr(
        tick_replay_service,
        "persist_tick_restore_run",
        lambda payload: persisted_payloads.append(payload) or {"id": 11, **payload},
    )

    started_at = datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc)
    completed_at = datetime(2026, 3, 20, 7, 5, 2, tzinfo=timezone.utc)
    time_values = iter([started_at, completed_at])
    monkeypatch.setattr(
        tick_replay_service,
        "utc_now",
        lambda: next(time_values),
    )

    result = tick_replay_service.create_tick_replay(
        archive_object_id=9,
        benchmark_profile_id="local_manual_v1",
        notes="smoke replay",
    )

    assert result["restore_status"] == "succeeded"
    assert result["restored_row_count"] == 1
    assert persisted_payloads[0]["throughput_gb_per_minute"] is not None


def test_create_tick_replay_omits_throughput_for_zero_elapsed_time(monkeypatch):
    persisted_payloads: list[dict] = []
    fixed_time = datetime(2026, 3, 20, 7, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(
        tick_replay_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: None,
    )
    monkeypatch.setattr(
        tick_replay_service,
        "get_tick_archive_object",
        lambda archive_object_id: {
            "id": archive_object_id,
            "object_key": "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
            "compressed_bytes": 1024 * 1024,
        },
    )
    monkeypatch.setattr(
        tick_replay_service,
        "read_archive_entries",
        lambda object_key: [
            {"raw_response_body": "{}", "fetch_timestamp": "2026-03-20T07:05:00+00:00"}
        ],
    )
    monkeypatch.setattr(
        tick_replay_service,
        "parse_archive_entry",
        lambda entry: [
            {
                "trading_date": date(2026, 3, 20),
                "observation_ts": fixed_time,
                "symbol": "2330",
                "market": "TW",
                "last_price": 1840.0,
                "last_size": 24094,
                "cumulative_volume": 46139,
                "best_bid_prices": [1840.0],
                "best_bid_sizes": [763],
                "best_ask_prices": [1845.0],
                "best_ask_sizes": [110],
                "source_name": "twse_public_snapshot",
                "parser_version": "twse_public_snapshot_parser_v1",
            }
        ],
    )
    monkeypatch.setattr(
        tick_replay_service,
        "replace_tick_observations",
        lambda archive_object_reference, observations: len(observations),
    )
    monkeypatch.setattr(
        tick_replay_service,
        "persist_tick_restore_run",
        lambda payload: persisted_payloads.append(payload) or {"id": 12, **payload},
    )
    monkeypatch.setattr(
        tick_replay_service,
        "utc_now",
        lambda: fixed_time,
    )

    result = tick_replay_service.create_tick_replay(
        archive_object_id=9,
        benchmark_profile_id="local_manual_v1",
    )

    assert result["throughput_gb_per_minute"] is None
    assert persisted_payloads[0]["throughput_gb_per_minute"] is None


def test_create_tick_replay_preserves_missing_archive_error(monkeypatch):
    monkeypatch.setattr(
        tick_replay_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: None,
    )
    monkeypatch.setattr(
        tick_replay_service,
        "get_tick_archive_object",
        lambda archive_object_id: (_ for _ in ()).throw(
            DataNotFoundError(
                f"Tick archive object '{archive_object_id}' was not found."
            )
        ),
    )

    with pytest.raises(DataNotFoundError, match="Tick archive object '9'"):
        tick_replay_service.create_tick_replay(
            archive_object_id=9,
            benchmark_profile_id="local_manual_v1",
        )


def test_create_tick_replay_preserves_missing_benchmark_profile_error(monkeypatch):
    monkeypatch.setattr(
        tick_replay_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: (_ for _ in ()).throw(
            DataNotFoundError(f"Benchmark profile '{profile_id}' was not found.")
        ),
    )

    with pytest.raises(DataNotFoundError, match="Benchmark profile 'missing'"):
        tick_replay_service.create_tick_replay(
            archive_object_id=9,
            benchmark_profile_id="missing",
        )


def test_get_tick_ops_kpi_summary_returns_all_tick_metrics(monkeypatch):
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "compressed_bytes": 100,
                "uncompressed_bytes": 300,
                "trading_date": date(2026, 3, 20),
            }
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "elapsed_seconds": 60.0,
                "throughput_gb_per_minute": 1.5,
                "compressed_bytes": 100,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            }
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    assert result["gate_id"] == "GATE-P2-OPS-001"
    assert set(result["metrics"]) == {
        "KPI-TICK-001",
        "KPI-TICK-002",
        "KPI-TICK-003",
    }
    assert result["metrics"]["KPI-TICK-001"]["status"] == "pass"
    assert result["selection_policy"]["max_compressed_gb_per_trading_day"] == 5.0
    assert result["binding_status"] == "exploratory"


def test_get_tick_ops_kpi_summary_excludes_incomplete_restore_windows(monkeypatch):
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "compressed_bytes": 1024,
                "uncompressed_bytes": 4096,
                "trading_date": date(2026, 3, 20),
            },
            {
                "compressed_bytes": 1024,
                "uncompressed_bytes": 4096,
                "trading_date": date(2026, 3, 20),
            },
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "elapsed_seconds": 60.0,
                "compressed_bytes": 1024,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            }
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    assert result["metrics"]["KPI-TICK-002"]["status"] == "fail"
    assert result["metrics"]["KPI-TICK-002"]["details"]["eligible_window_count"] == 0


def test_get_tick_ops_kpi_summary_uses_latest_succeeded_archive_run_per_day(
    monkeypatch,
):
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "id": 10,
                "run_id": 100,
                "compressed_bytes": 100,
                "uncompressed_bytes": 300,
                "trading_date": date(2026, 3, 20),
                "created_at": datetime(2026, 3, 20, 7, 10, tzinfo=timezone.utc),
                "run_created_at": datetime(2026, 3, 20, 7, 0, tzinfo=timezone.utc),
                "run_completed_at": datetime(2026, 3, 20, 7, 1, tzinfo=timezone.utc),
            },
            {
                "id": 11,
                "run_id": 101,
                "compressed_bytes": 110,
                "uncompressed_bytes": 330,
                "trading_date": date(2026, 3, 20),
                "created_at": datetime(2026, 3, 20, 8, 10, tzinfo=timezone.utc),
                "run_created_at": datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
                "run_completed_at": datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc),
            },
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "archive_object_id": 11,
                "elapsed_seconds": 60.0,
                "restore_started_at": datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
                "restore_completed_at": datetime(
                    2026, 3, 20, 8, 1, tzinfo=timezone.utc
                ),
                "compressed_bytes": 110,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            }
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    assert result["metrics"]["KPI-TICK-002"]["status"] == "pass"
    assert result["metrics"]["KPI-TICK-002"]["details"]["eligible_window_count"] == 1
    assert result["metrics"]["KPI-TICK-003"]["details"]["sample_count"] == 1


def test_get_tick_ops_kpi_summary_uses_window_wall_clock_for_parallel_restores(
    monkeypatch,
):
    compressed_bytes = 256 * 1024 * 1024
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "id": 21,
                "run_id": 210,
                "compressed_bytes": compressed_bytes,
                "uncompressed_bytes": compressed_bytes * 2,
                "trading_date": date(2026, 3, 20),
                "created_at": datetime(2026, 3, 20, 8, 10, tzinfo=timezone.utc),
                "run_created_at": datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
                "run_completed_at": datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc),
            },
            {
                "id": 22,
                "run_id": 210,
                "compressed_bytes": compressed_bytes,
                "uncompressed_bytes": compressed_bytes * 2,
                "trading_date": date(2026, 3, 20),
                "created_at": datetime(2026, 3, 20, 8, 11, tzinfo=timezone.utc),
                "run_created_at": datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
                "run_completed_at": datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc),
            },
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "archive_object_id": 21,
                "elapsed_seconds": 120.0,
                "restore_started_at": datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
                "restore_completed_at": datetime(
                    2026, 3, 20, 8, 2, tzinfo=timezone.utc
                ),
                "compressed_bytes": compressed_bytes,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            },
            {
                "archive_object_id": 22,
                "elapsed_seconds": 120.0,
                "restore_started_at": datetime(2026, 3, 20, 8, 1, tzinfo=timezone.utc),
                "restore_completed_at": datetime(
                    2026, 3, 20, 8, 3, tzinfo=timezone.utc
                ),
                "compressed_bytes": compressed_bytes,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            },
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    expected_throughput = 0.5 / 3.0
    assert result["metrics"]["KPI-TICK-002"]["value"] == pytest.approx(3.0)
    assert result["metrics"]["KPI-TICK-003"]["value"] == pytest.approx(
        expected_throughput
    )
    assert result["selection_policy"]["restore_time_model"] == "window_wall_clock"


def test_get_tick_ops_kpi_summary_deduplicates_replayed_archive_objects(monkeypatch):
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "id": 10,
                "compressed_bytes": 100,
                "uncompressed_bytes": 300,
                "trading_date": date(2026, 3, 20),
            },
            {
                "id": 11,
                "compressed_bytes": 100,
                "uncompressed_bytes": 300,
                "trading_date": date(2026, 3, 20),
            },
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "archive_object_id": 10,
                "elapsed_seconds": 60.0,
                "compressed_bytes": 100,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            },
            {
                "archive_object_id": 10,
                "elapsed_seconds": 55.0,
                "compressed_bytes": 100,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            },
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    assert result["metrics"]["KPI-TICK-002"]["details"]["eligible_window_count"] == 0
    assert result["metrics"]["KPI-TICK-003"]["details"]["sample_count"] == 0


def test_get_tick_ops_kpi_summary_excludes_zero_elapsed_throughput_samples(monkeypatch):
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_recent_tick_archive_trading_dates",
        lambda limit=20, statuses=None: [date(2026, 3, 20)],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_archive_objects_for_dates",
        lambda trading_dates, run_statuses=None: [
            {
                "id": 10,
                "compressed_bytes": 100,
                "uncompressed_bytes": 300,
                "trading_date": date(2026, 3, 20),
            }
        ],
    )
    monkeypatch.setattr(
        tick_ops_kpi_service,
        "list_tick_restore_runs_for_dates",
        lambda trading_dates, benchmark_only=True, archive_run_statuses=None, restore_statuses=None: [
            {
                "archive_object_id": 10,
                "elapsed_seconds": 0.0,
                "compressed_bytes": 100,
                "trading_date": date(2026, 3, 20),
                "benchmark_profile_id": "local_manual_v1",
            }
        ],
    )

    result = tick_ops_kpi_service.get_tick_ops_kpi_summary()

    assert result["metrics"]["KPI-TICK-003"]["details"]["sample_count"] == 0
    assert result["metrics"]["KPI-TICK-003"]["value"] is None


def test_get_tick_phase_gate_summary_reports_artifacts(monkeypatch):
    archive_path = "/tmp/tick-archive-test.jsonl.gz"

    class _ArchiveObject:
        id = 7
        object_key = "var/tick_archives/TW/2026-03-20/7/part-00001.jsonl.gz"
        archive_layout_version = "twse_public_observation_v1"
        retention_class = "provisional_until_tbd_002_resolved"
        checksum = "abc123"
        storage_backend = "local_filesystem"

    class _RestoreRun:
        id = 13
        archive_object_id = 7
        restore_status = "succeeded"
        elapsed_seconds = 12.0
        throughput_gb_per_minute = 0.5

    class _ExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return SimpleNamespace(first=lambda: self._value)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            text = str(stmt)
            if "tick_archive_objects" in text:
                return _ExecuteResult(_ArchiveObject())
            if "tick_restore_runs" in text:
                return _ExecuteResult(_RestoreRun())
            raise AssertionError(text)

        def scalar(self, stmt):
            text = str(stmt)
            if "tick_restore_runs" in text:
                return 2
            if "archive_object_reference" in text:
                return 12
            return 0

    monkeypatch.setattr(tick_gate_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        tick_gate_service,
        "archive_object_exists",
        lambda object_key, storage_backend: True,
    )

    result = tick_gate_service.get_tick_phase_gate_summary()

    assert result["gate_id"] == "GATE-P2-001"
    assert result["overall_status"] == "pass"
    assert result["artifacts"]["raw_tick_archive"]["details"]["path_exists"] is True
    assert (
        result["artifacts"]["normalized_replay_path"]["details"][
            "latest_restore_status"
        ]
        == "succeeded"
    )
    assert (
        result["artifacts"]["normalized_replay_path"]["details"][
            "latest_archive_object_id"
        ]
        == 7
    )
    assert result["artifacts"]["retention_policy"]["status"] == "pass"
    assert (
        result["artifacts"]["retention_policy"]["details"]["actual_retention_class"]
        == "provisional_until_tbd_002_resolved"
    )
    assert result["artifacts"]["restore_telemetry"]["status"] == "pass"
    assert (
        result["artifacts"]["restore_telemetry"]["details"]["latest_elapsed_seconds"]
        == 12.0
    )


def test_get_tick_phase_gate_summary_fails_when_latest_replay_failed(monkeypatch):
    class _ArchiveObject:
        id = 7
        object_key = "var/tick_archives/TW/2026-03-20/7/part-00001.jsonl.gz"
        archive_layout_version = "twse_public_observation_v1"
        retention_class = "provisional_until_tbd_002_resolved"
        checksum = "abc123"
        storage_backend = "local_filesystem"

    class _RestoreRun:
        id = 14
        archive_object_id = 8
        restore_status = "failed"
        elapsed_seconds = None
        throughput_gb_per_minute = None

    class _ExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return SimpleNamespace(first=lambda: self._value)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            text = str(stmt)
            if "tick_archive_objects" in text:
                return _ExecuteResult(_ArchiveObject())
            if "tick_restore_runs" in text:
                return _ExecuteResult(_RestoreRun())
            raise AssertionError(text)

        def scalar(self, stmt):
            text = str(stmt)
            if "tick_restore_runs" in text:
                return 3
            if "archive_object_reference" in text:
                return 20
            return 0

    monkeypatch.setattr(tick_gate_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        tick_gate_service,
        "archive_object_exists",
        lambda object_key, storage_backend: True,
    )

    result = tick_gate_service.get_tick_phase_gate_summary()

    assert result["artifacts"]["normalized_replay_path"]["status"] == "fail"
    assert (
        result["artifacts"]["normalized_replay_path"]["details"][
            "latest_restore_status"
        ]
        == "failed"
    )
    assert result["artifacts"]["restore_telemetry"]["status"] == "fail"


def test_get_tick_phase_gate_summary_uses_restore_for_latest_archive_object(
    monkeypatch,
):
    class _ArchiveObject:
        id = 9
        object_key = "var/tick_archives/TW/2026-03-20/9/part-00001.jsonl.gz"
        archive_layout_version = "twse_public_observation_v1"
        retention_class = "provisional_until_tbd_002_resolved"
        checksum = "abc123"
        storage_backend = "local_filesystem"

    class _RestoreRun:
        id = 22
        archive_object_id = 9
        restore_status = "failed"
        elapsed_seconds = None
        throughput_gb_per_minute = None

    class _ExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return SimpleNamespace(first=lambda: self._value)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            text = str(stmt)
            if "tick_archive_objects" in text:
                return _ExecuteResult(_ArchiveObject())
            if "archive_object_id" in text:
                return _ExecuteResult(_RestoreRun())
            raise AssertionError(text)

        def scalar(self, stmt):
            text = str(stmt)
            if "tick_restore_runs" in text:
                return 5
            if "archive_object_reference" in text:
                return 4
            return 0

    monkeypatch.setattr(tick_gate_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        tick_gate_service,
        "archive_object_exists",
        lambda object_key, storage_backend: True,
    )

    result = tick_gate_service.get_tick_phase_gate_summary()

    assert result["artifacts"]["normalized_replay_path"]["status"] == "fail"
    assert (
        result["artifacts"]["normalized_replay_path"]["details"][
            "latest_archive_object_id"
        ]
        == 9
    )
    assert (
        result["artifacts"]["normalized_replay_path"]["details"][
            "latest_restore_run_id"
        ]
        == 22
    )
    assert result["artifacts"]["restore_telemetry"]["status"] == "fail"


def test_get_tick_phase_gate_summary_reports_storage_backend_existence_errors(
    monkeypatch,
):
    class _ArchiveObject:
        id = 9
        object_key = "s3://bucket/object"
        archive_layout_version = "twse_public_observation_v1"
        retention_class = "provisional_until_tbd_002_resolved"
        checksum = "abc123"
        storage_backend = "remote_object_store"

    class _ExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return SimpleNamespace(first=lambda: self._value)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            text = str(stmt)
            if "tick_archive_objects" in text:
                return _ExecuteResult(_ArchiveObject())
            if "archive_object_id" in text:
                return _ExecuteResult(None)
            raise AssertionError(text)

        def scalar(self, stmt):
            if "tick_restore_runs" in str(stmt):
                return 0
            return 0

    monkeypatch.setattr(tick_gate_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        tick_gate_service,
        "archive_object_exists",
        lambda object_key, storage_backend: (_ for _ in ()).throw(
            ValueError(f"Unsupported tick archive storage backend: {storage_backend}")
        ),
    )

    result = tick_gate_service.get_tick_phase_gate_summary()

    assert result["artifacts"]["raw_tick_archive"]["status"] == "fail"
    assert (
        "Unsupported tick archive storage backend"
        in result["artifacts"]["raw_tick_archive"]["details"]["existence_check_error"]
    )


def test_get_tick_phase_gate_summary_fails_when_latest_archive_policy_mismatches(
    monkeypatch,
):
    class _ArchiveObject:
        id = 12
        object_key = "var/tick_archives/TW/2026-03-20/12/part-00001.jsonl.gz"
        archive_layout_version = "legacy_layout_v0"
        retention_class = "legacy_policy"
        checksum = "abc123"
        storage_backend = "local_filesystem"

    class _RestoreRun:
        id = 31
        archive_object_id = 12
        restore_status = "succeeded"
        elapsed_seconds = 5.0
        throughput_gb_per_minute = 0.25

    class _ExecuteResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return SimpleNamespace(first=lambda: self._value)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            text = str(stmt)
            if "tick_archive_objects" in text:
                return _ExecuteResult(_ArchiveObject())
            if "tick_restore_runs" in text:
                return _ExecuteResult(_RestoreRun())
            raise AssertionError(text)

        def scalar(self, stmt):
            text = str(stmt)
            if "tick_restore_runs" in text:
                return 1
            if "archive_object_reference" in text:
                return 5
            return 0

    monkeypatch.setattr(tick_gate_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        tick_gate_service,
        "archive_object_exists",
        lambda object_key, storage_backend: True,
    )

    result = tick_gate_service.get_tick_phase_gate_summary()

    assert result["artifacts"]["retention_policy"]["status"] == "fail"
    assert (
        result["artifacts"]["retention_policy"]["details"]["actual_retention_class"]
        == "legacy_policy"
    )
    assert (
        result["artifacts"]["retention_policy"]["details"][
            "actual_archive_layout_version"
        ]
        == "legacy_layout_v0"
    )
