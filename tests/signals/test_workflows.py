from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.research.services._foundation_flow as foundation_service
from backend.database import Base, DailyOHLCV, SymbolLifecycleRecord, TwCompanyProfile
from backend.platform.errors import DataNotFoundError, UnsupportedConfigurationError
from backend.research.contracts.runs import ResearchRunCreateRequest
from backend.signals.contracts._legacy import (
    AdaptiveTrainingRunRequest,
    LiveOrderRequest,
    SimulationOrderRequest,
)


def _make_research_request(**overrides) -> ResearchRunCreateRequest:
    payload = {
        "runtime_mode": "runtime_compatibility_mode",
        "market": "TW",
        "symbols": ["2330"],
        "date_range": {"start": "2024-01-02", "end": "2024-01-08"},
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": [{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        "model": {"type": "xgboost", "params": {}},
        "strategy": {
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 3,
            "allow_proactive_sells": True,
        },
        "execution": {"slippage": 0.001, "fees": 0.002},
        "baselines": [],
    }
    payload.update(overrides)
    return ResearchRunCreateRequest(**payload)


def test_create_simulation_order_rejects_unknown_run_id(monkeypatch):
    monkeypatch.setattr(
        foundation_service,
        "get_research_run_record",
        lambda run_id: (_ for _ in ()).throw(
            DataNotFoundError(f"Research run '{run_id}' was not found.")
        ),
    )

    with pytest.raises(DataNotFoundError, match="missing_run"):
        foundation_service.create_simulation_order(
            SimulationOrderRequest(
                run_id="missing_run",
                market="TW",
                symbol="2330",
                side="buy",
                quantity=100,
                requested_price=610,
            )
        )


def test_create_live_order_rejects_unknown_run_id(monkeypatch):
    monkeypatch.setattr(
        foundation_service,
        "get_research_run_record",
        lambda run_id: (_ for _ in ()).throw(
            DataNotFoundError(f"Research run '{run_id}' was not found.")
        ),
    )

    with pytest.raises(DataNotFoundError, match="missing_run"):
        foundation_service.create_live_order(
            LiveOrderRequest(
                run_id="missing_run",
                market="TW",
                symbol="2330",
                side="buy",
                quantity=100,
                requested_price=610,
                live_control_profile_id="live_control_v1",
                manual_confirmed=True,
            )
        )


def test_dispatch_run_execution_route_requires_explicit_manual_confirmation(
    monkeypatch,
):
    persisted_orders: list[dict[str, object]] = []
    captured_profiles: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        foundation_service,
        "ensure_default_failure_taxonomies",
        lambda: None,
    )
    monkeypatch.setattr(
        foundation_service,
        "get_effective_kill_switch",
        lambda market: None,
    )
    monkeypatch.setattr(
        foundation_service,
        "persist_execution_order",
        lambda order, **kwargs: persisted_orders.append(order) or {"order": order},
    )
    monkeypatch.setattr(
        foundation_service,
        "ensure_live_control_profile",
        lambda profile_id, market, live_control_version: (
            captured_profiles.append((profile_id, market, live_control_version))
            or {
                "id": profile_id,
                "market": market,
                "live_control_version": live_control_version,
            }
        ),
    )

    request = _make_research_request(
        execution_route="live_stub_v1",
        live_control_profile_id="live_ctrl_v1",
        manual_confirmed=False,
    )

    foundation_service.dispatch_run_execution_route(
        run_id="run_live",
        request=request,
        signals=[{"symbol": "2330", "position": 1.0, "score": 0.12}],
    )

    assert persisted_orders[0]["live_control_profile_id"] == "live_ctrl_v1"
    assert persisted_orders[0]["manual_confirmation"] is False
    assert persisted_orders[0]["status"] == "rejected"
    assert persisted_orders[0]["failure_code"] == "manual_confirmation_missing"
    assert captured_profiles == [
        ("live_ctrl_v1", "TW", foundation_service.LIVE_CONTROL_VERSION)
    ]


def test_create_external_signal_ingestion_treats_vendor_timestamp_as_exact(
    monkeypatch,
):
    captured_rows: list[dict[str, object]] = []

    monkeypatch.setattr(
        foundation_service,
        "_load_source_rows",
        lambda **kwargs: (
            [],
            [],
            [
                SimpleNamespace(
                    symbol="2330",
                    event_type="cash_dividend",
                    effective_date=date(2024, 1, 4),
                    event_publication_ts=datetime(
                        2024, 1, 3, 9, 0, tzinfo=timezone.utc
                    ),
                    timestamp_source_class="vendor_published",
                    source_name="vendor_feed",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        foundation_service,
        "persist_external_signal_ingestion",
        lambda archive_payload, signal_rows: (
            captured_rows.extend(signal_rows)
            or {"id": 1, "record_count": len(signal_rows)}
        ),
    )

    foundation_service.create_external_signal_ingestion(
        foundation_service.ExternalSignalIngestionRequest(
            source_family=foundation_service.EXTERNAL_SOURCE_FAMILY,
            market="TW",
            coverage_start=date(2024, 1, 1),
            coverage_end=date(2024, 1, 31),
            notes=None,
        )
    )

    assert captured_rows[0]["availability_mode"] == "exact"


def test_create_external_signal_audit_preserves_fallback_denominator(monkeypatch):
    records = []
    for idx in range(1, 61):
        availability_mode = "fallback" if idx > 40 else "exact"
        records.append(
            {
                "id": idx,
                "source_family": foundation_service.EXTERNAL_SOURCE_FAMILY,
                "market": "TW",
                "effective_date": date(2024, 1, idx if idx <= 31 else idx - 29),
                "availability_mode": availability_mode,
            }
        )
    persisted_payload: dict[str, object] = {}

    monkeypatch.setattr(
        foundation_service,
        "list_external_signal_records_for_window",
        lambda **kwargs: records,
    )
    monkeypatch.setattr(
        foundation_service,
        "persist_external_signal_audit",
        lambda payload: persisted_payload.update(payload) or payload,
    )

    result = foundation_service.create_external_signal_audit(
        foundation_service.ExternalSignalAuditRequest(
            source_family=foundation_service.EXTERNAL_SOURCE_FAMILY,
            market="TW",
            audit_window_start=date(2024, 1, 1),
            audit_window_end=date(2024, 2, 1),
        )
    )

    assert result["sample_size"] == 50
    assert result["fallback_sample_size"] == 20
    assert len(result["result"]["fallback_record_ids"]) == 20
    assert result["result"]["source_window_record_count"] == 60


def test_load_cluster_frame_uses_point_in_time_universe(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(foundation_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        session.add_all(
            [
                TwCompanyProfile(
                    symbol="1111",
                    market="TW",
                    exchange="TWSE",
                    board="listed",
                    company_name="Historical Active",
                    listing_date=date(2020, 1, 1),
                    trading_status="delisted",
                    source_name="seed",
                ),
                TwCompanyProfile(
                    symbol="2222",
                    market="TW",
                    exchange="TWSE",
                    board="listed",
                    company_name="Already Delisted",
                    listing_date=date(2020, 1, 1),
                    trading_status="active",
                    source_name="seed",
                ),
                TwCompanyProfile(
                    symbol="2330",
                    market="TW",
                    exchange="TWSE",
                    board="listed",
                    company_name="Stable Active",
                    listing_date=date(2020, 1, 1),
                    trading_status="active",
                    source_name="seed",
                ),
                SymbolLifecycleRecord(
                    symbol="1111",
                    market="TW",
                    event_type="listing",
                    effective_date=date(2020, 1, 1),
                    source_name="seed",
                ),
                SymbolLifecycleRecord(
                    symbol="1111",
                    market="TW",
                    event_type="delisting",
                    effective_date=date(2024, 1, 10),
                    source_name="seed",
                ),
                SymbolLifecycleRecord(
                    symbol="2222",
                    market="TW",
                    event_type="listing",
                    effective_date=date(2020, 1, 1),
                    source_name="seed",
                ),
                SymbolLifecycleRecord(
                    symbol="2222",
                    market="TW",
                    event_type="delisting",
                    effective_date=date(2024, 1, 4),
                    source_name="seed",
                ),
                DailyOHLCV(
                    market="TW",
                    symbol="1111",
                    date=date(2024, 1, 5),
                    source="seed",
                    open=10.0,
                    high=10.5,
                    low=9.5,
                    close=10.2,
                    volume=1000,
                ),
                DailyOHLCV(
                    market="TW",
                    symbol="2222",
                    date=date(2024, 1, 5),
                    source="seed",
                    open=20.0,
                    high=20.5,
                    low=19.5,
                    close=20.2,
                    volume=2000,
                ),
                DailyOHLCV(
                    market="TW",
                    symbol="2330",
                    date=date(2024, 1, 5),
                    source="seed",
                    open=30.0,
                    high=30.5,
                    low=29.5,
                    close=30.2,
                    volume=3000,
                ),
            ]
        )
        session.commit()

    symbols, frame = foundation_service._load_cluster_frame(
        market="TW", trading_date=date(2024, 1, 5)
    )

    assert symbols == ["1111", "2330"]
    assert list(frame.index) == ["1111", "2330"]


def test_persist_run_peer_outputs_uses_market_scoped_snapshot(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        foundation_service,
        "list_cluster_snapshots",
        lambda limit=200: [
            {
                "id": 1,
                "snapshot_version": "peer_cluster_kmeans_v1",
                "market": "US",
                "trading_date": date(2024, 1, 2),
            },
            {
                "id": 2,
                "snapshot_version": "peer_cluster_kmeans_v1",
                "market": "TW",
                "trading_date": date(2024, 1, 3),
            },
        ],
    )
    monkeypatch.setattr(
        foundation_service,
        "get_cluster_snapshot",
        lambda snapshot_id: {
            "id": snapshot_id,
            "snapshot_version": "peer_cluster_kmeans_v1",
            "market": "TW" if snapshot_id == 2 else "US",
            "trading_date": date(2024, 1, 3),
            "memberships": [
                {
                    "symbol": "2330",
                    "cluster_label": "cluster_0",
                    "distance_to_centroid": 0.1,
                },
                {
                    "symbol": "2317",
                    "cluster_label": "cluster_0",
                    "distance_to_centroid": 0.2,
                },
            ],
        },
    )
    monkeypatch.setattr(
        foundation_service,
        "persist_peer_feature_run",
        lambda run_payload, overlays: (
            captured.update({"run_payload": run_payload, "overlays": overlays})
            or {"id": 10}
        ),
    )

    result = foundation_service.persist_run_peer_outputs(
        run_id="run_tw",
        request=_make_research_request(
            market="TW",
            cluster_snapshot_version="peer_cluster_kmeans_v1",
            peer_policy_version="cluster_nearest_neighbors_v1",
        ),
    )

    assert result == {"id": 10}
    assert captured["run_payload"]["snapshot_id"] == 2
    assert captured["run_payload"]["market"] == "TW"


def test_market_close_ts_uses_tw_market_timezone():
    result = foundation_service._market_close_ts(date(2024, 1, 2))

    assert result.tzinfo == timezone.utc
    assert result.hour == 5
    assert result.minute == 30


def test_create_adaptive_training_run_requires_profile_contract_match(monkeypatch):
    monkeypatch.setattr(
        foundation_service,
        "get_adaptive_profile",
        lambda profile_id: {
            "id": profile_id,
            "reward_definition_version": "reward_v1",
            "state_definition_version": "state_v1",
            "rollout_control_version": "rollout_v1",
        },
    )

    with pytest.raises(UnsupportedConfigurationError, match="Mismatched fields"):
        foundation_service.create_adaptive_training_run_record(
            AdaptiveTrainingRunRequest(
                adaptive_profile_id="adaptive_shadow_v1",
                market="TW",
                adaptive_mode="shadow",
                reward_definition_version="reward_v2",
                state_definition_version="state_v1",
                rollout_control_version="rollout_v1",
            )
        )


def test_create_live_order_ensures_default_live_control_profile(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        foundation_service,
        "ensure_default_failure_taxonomies",
        lambda: None,
    )
    monkeypatch.setattr(
        foundation_service,
        "ensure_live_control_profile",
        lambda profile_id, market, live_control_version: {
            "id": profile_id,
            "market": market,
            "live_control_version": live_control_version,
        },
    )
    monkeypatch.setattr(
        foundation_service,
        "get_effective_kill_switch",
        lambda market: None,
    )
    monkeypatch.setattr(
        foundation_service,
        "persist_execution_order",
        lambda order, **kwargs: captured.update({"order": order, **kwargs}) or captured,
    )

    foundation_service.create_live_order(
        LiveOrderRequest(
            run_id=None,
            market="TW",
            symbol="2330",
            side="buy",
            quantity=100,
            requested_price=610,
            live_control_profile_id=None,
            manual_confirmed=True,
        )
    )

    assert captured["order"]["live_control_profile_id"] == "live_stub_default_v1"
