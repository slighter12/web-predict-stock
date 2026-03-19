from types import SimpleNamespace

import pytest

import backend.services.recovery_service as recovery_service
import backend.services.replay_service as replay_service
from backend.errors import DataAccessError, UnsupportedConfigurationError


def _raise_value_error(raw_record):
    raise ValueError("bad payload")


def _raise_data_access_error(payload):
    raise DataAccessError("db unavailable")


def _raise_recovery_configuration_error(**kwargs):
    raise UnsupportedConfigurationError("bad recovery config")


def test_replay_preserves_value_error_when_failure_audit_write_fails(monkeypatch):
    monkeypatch.setattr(
        replay_service,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            id=raw_payload_id,
            source_name="yfinance",
            symbol="2330",
            market="TW",
            parser_version="v1",
        ),
    )
    monkeypatch.setattr(
        replay_service.scraper,
        "replay_raw_ingest_record",
        _raise_value_error,
    )
    monkeypatch.setattr(
        replay_service,
        "persist_replay_record",
        _raise_data_access_error,
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad payload"):
        replay_service.replay_raw_payload(raw_payload_id=1)


def test_recovery_preserves_rejection_when_failure_audit_write_fails(monkeypatch):
    monkeypatch.setattr(
        recovery_service,
        "get_latest_successful_raw_ingest",
        lambda: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        _raise_recovery_configuration_error,
    )
    monkeypatch.setattr(
        recovery_service,
        "persist_recovery_record",
        _raise_data_access_error,
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad recovery config"):
        recovery_service.create_recovery_drill(raw_payload_id=None)
