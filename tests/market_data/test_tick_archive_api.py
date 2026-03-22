from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import backend.market_data.api as data_plane_api
from backend.app import app
from backend.platform.errors import DataNotFoundError, ExternalFetchError

client = TestClient(app)


def test_tick_archive_endpoints(monkeypatch):
    created_at = datetime.now(timezone.utc)
    run_payload = {
        "id": 1,
        "source_name": "twse_public_snapshot",
        "market": "TW",
        "trading_date": date(2026, 3, 20),
        "trigger_mode": "post_close_crawl",
        "scope": "full_market",
        "status": "succeeded",
        "notes": "manual dispatch",
        "symbol_count": 1200,
        "request_count": 24,
        "observation_count": 1180,
        "started_at": created_at,
        "completed_at": created_at,
        "abort_reason": None,
        "created_at": created_at,
    }
    archive_payload = {
        "id": 5,
        "run_id": 1,
        "storage_backend": "local_filesystem",
        "object_key": "var/tick_archives/TW/2026-03-20/1/part-00001.jsonl.gz",
        "compression_codec": "gzip",
        "archive_layout_version": "twse_public_observation_v1",
        "compressed_bytes": 1024,
        "uncompressed_bytes": 4096,
        "compression_ratio": 0.75,
        "record_count": 50,
        "first_observation_ts": created_at,
        "last_observation_ts": created_at,
        "checksum": "abc123",
        "retention_class": "provisional_until_tbd_002_resolved",
        "created_at": created_at,
    }
    replay_payload = {
        "id": 9,
        "archive_object_id": 5,
        "benchmark_profile_id": "local_manual_v1",
        "notes": None,
        "restore_status": "succeeded",
        "restored_row_count": 50,
        "restore_started_at": created_at,
        "restore_completed_at": created_at,
        "elapsed_seconds": 12.0,
        "throughput_gb_per_minute": 0.5,
        "abort_reason": None,
        "created_at": created_at,
    }
    kpi_payload = {
        "gate_id": "GATE-P2-OPS-001",
        "overall_status": "pass",
        "binding_status": "exploratory",
        "binding_reason": "TBD-002 remains open.",
        "metrics": {
            "KPI-TICK-001": {
                "value": 75.0,
                "status": "pass",
                "numerator": 3000.0,
                "denominator": 4000.0,
                "unit": "percent",
                "window": "rolling 20 trading days",
                "details": {"sample_count": 1},
            }
        },
        "selection_policy": {
            "max_compressed_gb_per_trading_day": 5.0,
            "benchmark_profile_required": True,
        },
    }
    gate_payload = {
        "gate_id": "GATE-P2-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": "pass",
        "artifacts": {
            "raw_tick_archive": {
                "status": "pass",
                "details": {"path_exists": True},
            }
        },
    }

    monkeypatch.setattr(
        data_plane_api,
        "create_tick_archive_dispatch",
        lambda request: run_payload,
    )
    monkeypatch.setattr(
        data_plane_api,
        "list_tick_archive_dispatches",
        lambda: [run_payload],
    )
    monkeypatch.setattr(
        data_plane_api,
        "create_tick_archive_import",
        lambda **kwargs: {"run": run_payload, "archive_object": archive_payload},
    )
    monkeypatch.setattr(
        data_plane_api,
        "list_tick_archives",
        lambda: [archive_payload],
    )
    monkeypatch.setattr(
        data_plane_api,
        "create_tick_replay",
        lambda **kwargs: replay_payload,
    )
    monkeypatch.setattr(
        data_plane_api,
        "list_tick_replays",
        lambda: [replay_payload],
    )
    monkeypatch.setattr(
        data_plane_api,
        "get_tick_ops_kpi_summary",
        lambda: kpi_payload,
    )
    monkeypatch.setattr(
        data_plane_api,
        "get_tick_phase_gate_summary",
        lambda: gate_payload,
    )

    dispatch_response = client.post(
        "/api/v1/data/tick-archive-dispatches",
        json={
            "market": "TW",
            "trading_date": "2026-03-20",
            "mode": "post_close_crawl",
        },
    )
    import_response = client.post(
        "/api/v1/data/tick-archive-imports",
        data={"market": "TW", "trading_date": "2026-03-20"},
        files={
            "archive_file": (
                "sample.jsonl.gz",
                b'{"raw_response_body":"{}","fetch_timestamp":"2026-03-20T07:05:00+00:00"}\n',
                "application/gzip",
            )
        },
    )
    replay_response = client.post(
        "/api/v1/data/tick-replays",
        json={"archive_object_id": 5, "benchmark_profile_id": "local_manual_v1"},
    )

    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["id"] == 1
    assert (
        client.get("/api/v1/data/tick-archive-dispatches").json()[0]["status"]
        == "succeeded"
    )
    assert import_response.status_code == 200
    assert import_response.json()["archive_object"]["id"] == 5
    assert client.get("/api/v1/data/tick-archives").json()[0]["run_id"] == 1
    assert replay_response.status_code == 200
    assert replay_response.json()["restore_status"] == "succeeded"
    assert client.get("/api/v1/data/tick-replays").json()[0]["id"] == 9
    assert (
        client.get("/api/v1/data/tick-ops/kpis").json()["gate_id"] == "GATE-P2-OPS-001"
    )
    assert client.get("/api/v1/data/tick-gates/p2").json()["gate_id"] == "GATE-P2-001"


def test_tick_archive_dispatch_returns_non_200_on_failure(monkeypatch):
    monkeypatch.setattr(
        data_plane_api,
        "create_tick_archive_dispatch",
        lambda request: (_ for _ in ()).throw(
            ExternalFetchError("upstream snapshot unavailable")
        ),
    )

    response = client.post(
        "/api/v1/data/tick-archive-dispatches",
        json={
            "market": "TW",
            "trading_date": "2026-03-20",
            "mode": "post_close_crawl",
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "EXTERNAL_FETCH_FAILED"


def test_tick_replay_returns_not_found_for_missing_resources(monkeypatch):
    monkeypatch.setattr(
        data_plane_api,
        "create_tick_replay",
        lambda **kwargs: (_ for _ in ()).throw(
            DataNotFoundError("Tick archive object '999' was not found.")
        ),
    )

    response = client.post(
        "/api/v1/data/tick-replays",
        json={"archive_object_id": 999, "benchmark_profile_id": "local_manual_v1"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
