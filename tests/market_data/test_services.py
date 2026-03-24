from datetime import datetime, timezone

import pytest

import backend.market_data.services.important_events as important_event_service
import backend.market_data.services.ingestion as data_ingestion_service
import backend.market_data.services.lifecycle as lifecycle_service
from backend.market_data.contracts.operations import (
    DataIngestionRequest,
    ImportantEventUpsert,
    LifecycleRecordUpsert,
)
from backend.platform.errors import DataAccessError, UnsupportedConfigurationError


def test_save_lifecycle_record_normalizes_payload(monkeypatch):
    captured: dict = {}

    def capture(payload):
        captured.update(payload)
        return {"id": 1, **payload}

    monkeypatch.setattr(lifecycle_service, "upsert_lifecycle_record", capture)

    record = lifecycle_service.save_lifecycle_record(
        LifecycleRecordUpsert(
            symbol=" 2330 ",
            market="TW",
            event_type="listing",
            effective_date="2000-01-01",
            reference_symbol=" ",
            source_name=" manual_data_plane ",
            archive_object_reference=" ",
            notes=" initial listing ",
        )
    )

    assert captured["symbol"] == "2330"
    assert captured["market"] == "TW"
    assert captured["source_name"] == "manual_data_plane"
    assert captured["reference_symbol"] is None
    assert captured["archive_object_reference"] is None
    assert captured["notes"] == "initial listing"
    assert record["id"] == 1


def test_save_important_event_normalizes_payload(monkeypatch):
    captured: dict = {}

    def capture(payload):
        captured.update(payload)
        return {"id": 7, **payload}

    monkeypatch.setattr(
        important_event_service, "upsert_important_event_record", capture
    )

    record = important_event_service.save_important_event(
        ImportantEventUpsert(
            symbol=" 2330 ",
            market="TW",
            event_type="cash_dividend",
            effective_date="2024-06-01",
            event_publication_ts=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
            timestamp_source_class="official_exchange",
            source_name=" manual_data_plane ",
            archive_object_reference=" ",
            notes=" cash dividend declared ",
        )
    )

    assert captured["symbol"] == "2330"
    assert captured["market"] == "TW"
    assert captured["source_name"] == "manual_data_plane"
    assert captured["archive_object_reference"] is None
    assert captured["notes"] == "cash dividend declared"
    assert record["id"] == 7


def test_ingest_market_data_normalizes_request(monkeypatch):
    captured: dict = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return {
            "symbol": kwargs["symbol"],
            "market": kwargs["market"],
            "backfill": {"raw_payload_id": 1},
            "daily_update": {"raw_payload_id": 2},
        }

    monkeypatch.setattr(data_ingestion_service.scraper, "ingest_symbol", capture)

    result = data_ingestion_service.ingest_market_data(
        DataIngestionRequest(
            symbol=" 2330 ",
            market="TW",
            years=5,
            date_str=" 2024-01-02 ",
        )
    )

    assert captured == {
        "symbol": "2330",
        "market": "TW",
        "years": 5,
        "date_str": "2024-01-02",
    }
    assert result["backfill"]["raw_payload_id"] == 1


def test_ingest_tw_market_batch_wraps_scraper(monkeypatch):
    captured: dict = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return {"upserted_rows": 2, "errors": []}

    monkeypatch.setattr(
        data_ingestion_service.scraper, "ingest_tw_market_batch", capture
    )

    result = data_ingestion_service.ingest_tw_market_batch(
        trading_date=datetime(2024, 1, 2, tzinfo=timezone.utc).date(),
        refresh_universe=True,
    )

    assert captured == {
        "trading_date": datetime(2024, 1, 2, tzinfo=timezone.utc).date(),
        "refresh_universe": True,
    }
    assert result["upserted_rows"] == 2


def test_ingest_market_data_wraps_value_error(monkeypatch):
    def raise_value_error(**kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(
        data_ingestion_service.scraper, "ingest_symbol", raise_value_error
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad input"):
        data_ingestion_service.ingest_market_data(
            DataIngestionRequest(symbol="2330", market="TW", years=5)
        )


def test_ingest_market_data_wraps_unexpected_error(monkeypatch):
    def raise_runtime_error(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        data_ingestion_service.scraper, "ingest_symbol", raise_runtime_error
    )

    with pytest.raises(DataAccessError, match="Failed to ingest market data."):
        data_ingestion_service.ingest_market_data(
            DataIngestionRequest(symbol="2330", market="TW", years=5)
        )


def test_ingest_tw_market_batch_wraps_unexpected_error(monkeypatch):
    monkeypatch.setattr(
        data_ingestion_service.scraper,
        "ingest_tw_market_batch",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    with pytest.raises(DataAccessError, match="Failed to ingest TW market batch data."):
        data_ingestion_service.ingest_tw_market_batch(
            trading_date=datetime(2024, 1, 2, tzinfo=timezone.utc).date()
        )


def test_ingest_tw_market_batch_wraps_value_error(monkeypatch):
    monkeypatch.setattr(
        data_ingestion_service.scraper,
        "ingest_tw_market_batch",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("empty universe")),
    )

    with pytest.raises(UnsupportedConfigurationError, match="empty universe"):
        data_ingestion_service.ingest_tw_market_batch(
            trading_date=datetime(2024, 1, 2, tzinfo=timezone.utc).date()
        )
