from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import backend.api.data_plane as data_plane_api
from backend.app import app

client = TestClient(app)


def test_create_data_ingestion(monkeypatch):
    monkeypatch.setattr(
        data_plane_api,
        "ingest_market_data",
        lambda request: {
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
        "trigger_mode": "manual",
        "schedule_id": None,
        "scheduled_for_date": None,
        "latest_replayable_day": date(2024, 1, 3),
        "completed_trading_day_delta": 1,
        "abort_reason": None,
        "drill_started_at": datetime.now(timezone.utc),
        "drill_completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    recovery_schedule_payload = {
        "id": 11,
        "market": "TW",
        "symbol": "2330",
        "cadence": "monthly",
        "day_of_month": 1,
        "timezone": "Asia/Taipei",
        "benchmark_profile_id": "monthly_recovery_v1",
        "notes": "smoke schedule",
        "is_active": True,
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
        data_plane_api,
        "create_recovery_drill_schedule",
        lambda request: recovery_schedule_payload,
    )
    monkeypatch.setattr(
        data_plane_api,
        "list_recovery_schedules",
        lambda: [recovery_schedule_payload],
    )
    monkeypatch.setattr(
        data_plane_api, "save_lifecycle_record", lambda request: lifecycle_payload
    )
    monkeypatch.setattr(data_plane_api, "list_lifecycle", lambda: [lifecycle_payload])
    monkeypatch.setattr(
        data_plane_api, "save_important_event", lambda request: important_event_payload
    )
    monkeypatch.setattr(
        data_plane_api, "list_important_events", lambda: [important_event_payload]
    )

    recovery_response = client.post("/api/v1/data/recovery-drills", json={})
    recovery_schedule_response = client.post(
        "/api/v1/data/recovery-drill-schedules",
        json={
            "market": "TW",
            "symbol": "2330",
            "cadence": "monthly",
            "day_of_month": 1,
            "timezone": "Asia/Taipei",
            "benchmark_profile_id": "monthly_recovery_v1",
        },
    )
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
    assert recovery_response.json()["trigger_mode"] == "manual"
    assert client.get("/api/v1/data/recovery-drills").json()[0]["id"] == 3
    assert recovery_schedule_response.status_code == 200
    assert recovery_schedule_response.json()["cadence"] == "monthly"
    assert client.get("/api/v1/data/recovery-drill-schedules").json()[0]["id"] == 11
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


def test_ops_watchlist_benchmark_and_crawler_endpoints(monkeypatch):
    created_at = datetime.now(timezone.utc)
    benchmark_profile = {
        "id": "one_week_rebuild_v1",
        "cpu_class": "m-class",
        "memory_size": "16gb",
        "storage_type": "ssd",
        "compression_settings": "none",
        "archive_layout_version": "raw_layout_v1",
        "network_class": "local",
        "created_at": created_at,
    }
    watchlist_entry = {
        "id": 1,
        "symbol": "2330",
        "market": "TW",
        "years": 5,
        "is_active": True,
        "created_at": created_at,
    }
    dispatch_summary = {
        "schedule_count": 1,
        "dispatched_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
        "records": [
            {
                "id": 8,
                "watchlist_id": 1,
                "symbol": "2330",
                "market": "TW",
                "scheduled_for_date": date(2026, 3, 20),
                "status": "succeeded",
                "attempt_count": 1,
                "last_error_message": None,
                "first_attempt_at": created_at,
                "last_attempt_at": created_at,
                "completed_at": created_at,
                "created_at": created_at,
                "attempts": [
                    {
                        "id": 3,
                        "attempt_number": 1,
                        "status": "succeeded",
                        "raw_payload_id": 41,
                        "error_message": None,
                        "started_at": created_at,
                        "completed_at": created_at,
                        "created_at": created_at,
                    }
                ],
            }
        ],
    }
    kpi_summary = {
        "gate_id": "GATE-P1-OPS-001",
        "overall_status": "pass",
        "metrics": {
            "KPI-DATA-001": {
                "value": 100.0,
                "status": "pass",
                "numerator": 20,
                "denominator": 20,
                "unit": "percent",
                "window": "rolling 20 trading days",
                "details": {},
            },
            "KPI-DATA-008": {
                "value": 5,
                "status": "pass",
                "numerator": 5,
                "denominator": 5,
                "unit": "events",
                "window": "rolling 90 calendar days",
                "details": {},
            },
        },
    }
    crawler_summary = {
        "source_name": "tw_official_lifecycle",
        "raw_payload_id": 91,
        "processed_count": 2,
        "upserted_count": 2,
        "errors": [],
    }

    monkeypatch.setattr(
        data_plane_api, "create_benchmark_profile", lambda request: benchmark_profile
    )
    monkeypatch.setattr(
        data_plane_api,
        "list_registered_benchmark_profiles",
        lambda: [benchmark_profile],
    )
    monkeypatch.setattr(
        data_plane_api,
        "create_ingestion_watchlist_entry",
        lambda request: watchlist_entry,
    )
    monkeypatch.setattr(data_plane_api, "list_ingestion_watchlist", lambda: [watchlist_entry])
    monkeypatch.setattr(
        data_plane_api,
        "dispatch_due_scheduled_ingestions",
        lambda scheduled_for_date=None: dispatch_summary,
    )
    monkeypatch.setattr(data_plane_api, "get_ops_kpi_summary", lambda: kpi_summary)
    monkeypatch.setattr(data_plane_api, "crawl_lifecycle_records", lambda: crawler_summary)
    monkeypatch.setattr(data_plane_api, "crawl_important_events", lambda: crawler_summary)

    benchmark_response = client.post(
        "/api/v1/data/benchmark-profiles",
        json={
            "id": "one_week_rebuild_v1",
            "cpu_class": "m-class",
            "memory_size": "16gb",
            "storage_type": "ssd",
            "compression_settings": "none",
            "archive_layout_version": "raw_layout_v1",
            "network_class": "local",
        },
    )
    watchlist_response = client.post(
        "/api/v1/data/ingestion-watchlist",
        json={"symbol": "2330", "market": "TW", "years": 5},
    )
    dispatch_response = client.post("/api/v1/data/ingestion-dispatches", json={})
    kpi_response = client.get("/api/v1/data/ops/kpis")
    lifecycle_crawl_response = client.post("/api/v1/data/lifecycle-crawls")
    important_event_crawl_response = client.post(
        "/api/v1/data/important-event-crawls"
    )

    assert benchmark_response.status_code == 200
    assert benchmark_response.json()["id"] == "one_week_rebuild_v1"
    assert client.get("/api/v1/data/benchmark-profiles").json()[0]["cpu_class"] == "m-class"
    assert watchlist_response.status_code == 200
    assert watchlist_response.json()["symbol"] == "2330"
    assert client.get("/api/v1/data/ingestion-watchlist").json()[0]["years"] == 5
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["records"][0]["attempts"][0]["raw_payload_id"] == 41
    assert kpi_response.status_code == 200
    assert kpi_response.json()["overall_status"] == "pass"
    assert lifecycle_crawl_response.status_code == 200
    assert lifecycle_crawl_response.json()["processed_count"] == 2
    assert important_event_crawl_response.status_code == 200
    assert important_event_crawl_response.json()["raw_payload_id"] == 91
