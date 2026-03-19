from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import backend.api.data_plane as data_plane_api
from backend.app import app

client = TestClient(app)


def test_create_data_ingestion(monkeypatch):
    monkeypatch.setattr(
        data_plane_api,
        "ingest_market_data",
        lambda **kwargs: {
            "symbol": "2330",
            "market": "TW",
            "backfill": {
                "raw_payload_id": 1,
                "archive_object_reference": "raw:1",
                "parser_version": "v1",
                "input_rows": 10,
                "validated_rows": 9,
                "dropped_rows": 1,
                "duplicates_removed": 0,
                "null_rows_removed": 0,
                "invalid_rows_removed": 1,
                "gap_warnings": 0,
                "upserted_rows": 9,
                "official_overrides": 0,
            },
            "daily_update": {
                "raw_payload_id": 2,
                "archive_object_reference": "raw:2",
                "parser_version": "v1",
                "input_rows": 2,
                "validated_rows": 2,
                "dropped_rows": 0,
                "duplicates_removed": 0,
                "null_rows_removed": 0,
                "invalid_rows_removed": 0,
                "gap_warnings": 0,
                "upserted_rows": 2,
                "official_overrides": 0,
            },
        },
    )

    response = client.post(
        "/api/v1/data/ingestions", json={"symbol": "2330", "market": "TW", "years": 5}
    )

    assert response.status_code == 200
    assert response.json()["backfill"]["raw_payload_id"] == 1


def test_replay_and_replay_list(monkeypatch):
    replay_payload = {
        "id": 9,
        "raw_payload_id": 1,
        "source_name": "yfinance",
        "symbol": "2330",
        "market": "TW",
        "archive_object_reference": "raw:1",
        "parser_version": "v1",
        "benchmark_profile_id": "local_manual_v1",
        "notes": None,
        "restore_status": "succeeded",
        "abort_reason": None,
        "restored_row_count": 9,
        "replay_started_at": datetime.now(timezone.utc),
        "replay_completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(
        data_plane_api, "replay_raw_payload", lambda **kwargs: replay_payload
    )
    monkeypatch.setattr(data_plane_api, "list_replays", lambda: [replay_payload])

    create_response = client.post("/api/v1/data/replays", json={"raw_payload_id": 1})
    list_response = client.get("/api/v1/data/replays")

    assert create_response.status_code == 200
    assert create_response.json()["id"] == 9
    assert list_response.status_code == 200
    assert list_response.json()[0]["restore_status"] == "succeeded"


def test_recovery_lifecycle_and_important_event_endpoints(monkeypatch):
    recovery_payload = {
        "id": 3,
        "raw_payload_id": 1,
        "replay_run_id": 9,
        "benchmark_profile_id": "local_manual_v1",
        "notes": None,
        "status": "succeeded",
        "latest_replayable_day": date(2024, 1, 3),
        "completed_trading_day_delta": 1,
        "abort_reason": None,
        "drill_started_at": datetime.now(timezone.utc),
        "drill_completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    lifecycle_payload = {
        "id": 5,
        "symbol": "2330",
        "market": "TW",
        "event_type": "listing",
        "effective_date": date(2000, 1, 1),
        "reference_symbol": None,
        "source_name": "manual_data_plane",
        "raw_payload_id": None,
        "archive_object_reference": None,
        "notes": "initial listing",
        "created_at": datetime.now(timezone.utc),
    }
    important_event_payload = {
        "id": 7,
        "symbol": "2330",
        "market": "TW",
        "event_type": "cash_dividend",
        "effective_date": date(2024, 6, 1),
        "event_publication_ts": datetime.now(timezone.utc),
        "timestamp_source_class": "official_exchange",
        "source_name": "manual_data_plane",
        "raw_payload_id": None,
        "archive_object_reference": None,
        "notes": "cash dividend declared",
        "created_at": datetime.now(timezone.utc),
    }

    monkeypatch.setattr(
        data_plane_api, "create_recovery_drill", lambda **kwargs: recovery_payload
    )
    monkeypatch.setattr(
        data_plane_api, "list_recovery_drills", lambda: [recovery_payload]
    )
    monkeypatch.setattr(
        data_plane_api, "save_lifecycle_record", lambda payload: lifecycle_payload
    )
    monkeypatch.setattr(data_plane_api, "list_lifecycle", lambda: [lifecycle_payload])
    monkeypatch.setattr(
        data_plane_api, "save_important_event", lambda payload: important_event_payload
    )
    monkeypatch.setattr(
        data_plane_api, "list_important_events", lambda: [important_event_payload]
    )

    recovery_response = client.post("/api/v1/data/recovery-drills", json={})
    lifecycle_response = client.post(
        "/api/v1/data/lifecycle-records",
        json={
            "symbol": "2330",
            "market": "TW",
            "event_type": "listing",
            "effective_date": "2000-01-01",
            "source_name": "manual_data_plane",
        },
    )
    important_event_response = client.post(
        "/api/v1/data/important-events",
        json={
            "symbol": "2330",
            "market": "TW",
            "event_type": "cash_dividend",
            "event_publication_ts": "2024-06-01T09:00:00Z",
            "timestamp_source_class": "official_exchange",
            "source_name": "manual_data_plane",
        },
    )

    assert recovery_response.status_code == 200
    assert recovery_response.json()["status"] == "succeeded"
    assert client.get("/api/v1/data/recovery-drills").json()[0]["id"] == 3
    assert lifecycle_response.status_code == 200
    assert (
        client.get("/api/v1/data/lifecycle-records").json()[0]["event_type"]
        == "listing"
    )
    assert important_event_response.status_code == 200
    assert (
        client.get("/api/v1/data/important-events").json()[0]["timestamp_source_class"]
        == "official_exchange"
    )
