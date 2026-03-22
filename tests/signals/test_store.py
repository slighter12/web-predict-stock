from datetime import date, datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import backend.signals.repositories._store as foundation_repository
from backend.database import (
    Base,
    ClusterMembership,
    ClusterSnapshot,
    ExecutionFailureTaxonomy,
    ExecutionFillEvent,
    ExecutionOrder,
    ExecutionOrderEvent,
    ExecutionPositionSnapshot,
    FactorCatalog,
    FactorCatalogEntry,
    LiveRiskCheck,
    PeerComparisonOverlay,
    PeerFeatureRun,
)


def _setup_session(monkeypatch, tables):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=tables)
    monkeypatch.setattr(foundation_repository, "SessionLocal", testing_session_local)
    return testing_session_local


def test_factor_catalog_repository_roundtrip(monkeypatch):
    _setup_session(
        monkeypatch,
        tables=[FactorCatalog.__table__, FactorCatalogEntry.__table__],
    )

    persisted = foundation_repository.persist_factor_catalog(
        {
            "id": "catalog_v1",
            "market": "TW",
            "source_family": "tw_company_event_layer_v1",
            "lineage_version": "tw_company_event_lineage_v1",
            "minimum_coverage_ratio": 0.8,
            "is_active": True,
            "notes": "seed",
            "entries": [
                {
                    "factor_id": "company_listing_age_days_v1",
                    "display_name": "Company Listing Age Days",
                    "formula_definition": "trading_date - listing_date",
                    "lineage": "tw_company_event_lineage_v1",
                    "timing_semantics": "fallback_listing_date_pti",
                    "missing_value_policy": "null_when_listing_date_unknown",
                    "scoring_eligible": True,
                },
                {
                    "factor_id": "important_event_count_30d_v1",
                    "display_name": "Important Event Count 30d",
                    "formula_definition": "count(events in trailing 30d)",
                    "lineage": "tw_company_event_lineage_v1",
                    "timing_semantics": "official_publication_ts_pti",
                    "missing_value_policy": "zero_when_no_events",
                    "scoring_eligible": False,
                },
            ],
        }
    )

    loaded = foundation_repository.get_factor_catalog("catalog_v1")
    listed = foundation_repository.list_factor_catalogs(limit=10)

    assert persisted["id"] == "catalog_v1"
    assert [entry["factor_id"] for entry in loaded["entries"]] == [
        "company_listing_age_days_v1",
        "important_event_count_30d_v1",
    ]
    assert loaded["entries"][0]["scoring_eligible"] is True
    assert listed[0]["id"] == "catalog_v1"


def test_execution_order_repository_roundtrip_with_full_ledger(monkeypatch):
    _setup_session(
        monkeypatch,
        tables=[
            ExecutionOrder.__table__,
            ExecutionOrderEvent.__table__,
            ExecutionFillEvent.__table__,
            ExecutionPositionSnapshot.__table__,
            LiveRiskCheck.__table__,
        ],
    )
    submitted_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    persisted = foundation_repository.persist_execution_order(
        {
            "run_id": "run_123",
            "route": "live_stub_v1",
            "market": "TW",
            "symbol": "2330",
            "side": "buy",
            "quantity": 100.0,
            "requested_price": 101.5,
            "status": "accepted_for_stub_dispatch",
            "simulation_profile_id": None,
            "live_control_profile_id": "live_ctrl_v1",
            "failure_code": None,
            "manual_confirmation": True,
            "rejection_reason": None,
            "submitted_at": submitted_at,
            "acknowledged_at": submitted_at,
        },
        events=[
            {"event_type": "submitted", "event_ts": submitted_at, "detail": {}},
            {
                "event_type": "filled",
                "event_ts": submitted_at,
                "detail": {"stub_execution": True},
            },
            {
                "event_type": "position_readback",
                "event_ts": submitted_at,
                "detail": {"position_symbol": "2330"},
            },
        ],
        fills=[
            {
                "fill_ts": submitted_at,
                "fill_price": 101.5,
                "quantity": 100.0,
                "slippage_bps": 0.0,
            }
        ],
        positions=[
            {
                "run_id": "run_123",
                "route": "live_stub_v1",
                "market": "TW",
                "symbol": "2330",
                "quantity": 100.0,
                "avg_price": 101.5,
                "snapshot_ts": submitted_at,
            }
        ],
        risk_checks=[
            {
                "status": "pass",
                "detail": {"notional": 10150.0},
                "checked_at": submitted_at,
            }
        ],
    )

    listed = foundation_repository.list_execution_orders(route="live_stub_v1", limit=10)

    assert persisted["status"] == "accepted_for_stub_dispatch"
    assert [event["event_type"] for event in persisted["events"]] == [
        "submitted",
        "filled",
        "position_readback",
    ]
    assert persisted["fills"][0]["fill_price"] == 101.5
    assert persisted["positions"][0]["symbol"] == "2330"
    assert persisted["risk_checks"][0]["detail"]["notional"] == 10150.0
    assert listed[0]["id"] == persisted["id"]


def test_cluster_snapshot_and_peer_feature_run_roundtrip(monkeypatch):
    _setup_session(
        monkeypatch,
        tables=[
            ClusterSnapshot.__table__,
            ClusterMembership.__table__,
            PeerFeatureRun.__table__,
            PeerComparisonOverlay.__table__,
        ],
    )

    snapshot = foundation_repository.persist_cluster_snapshot(
        {
            "snapshot_version": "peer_cluster_kmeans_v1",
            "run_id": None,
            "factor_catalog_version": "catalog_v1",
            "market": "TW",
            "trading_date": date(2026, 3, 21),
            "cluster_count": 2,
            "symbol_count": 3,
            "status": "succeeded",
            "notes": "seed",
        },
        [
            {
                "symbol": "1101",
                "cluster_label": "cluster_0",
                "distance_to_centroid": 0.1,
            },
            {
                "symbol": "1216",
                "cluster_label": "cluster_0",
                "distance_to_centroid": 0.2,
            },
            {
                "symbol": "2330",
                "cluster_label": "cluster_1",
                "distance_to_centroid": 0.3,
            },
        ],
    )
    peer_run = foundation_repository.persist_peer_feature_run(
        {
            "run_id": "run_123",
            "snapshot_id": snapshot["id"],
            "peer_policy_version": "cluster_nearest_neighbors_v1",
            "market": "TW",
            "trading_date": date(2026, 3, 21),
            "status": "succeeded",
            "produced_feature_count": 2,
            "warning_count": 1,
            "warnings": ["2330 had no peers."],
        },
        [
            {
                "symbol": "1101",
                "peer_symbol_count": 1,
                "peer_feature_value": 1.0,
                "detail": {"peer_symbols": ["1216"]},
            },
            {
                "symbol": "2330",
                "peer_symbol_count": 0,
                "peer_feature_value": 0.0,
                "detail": {"peer_symbols": []},
            },
        ],
    )

    loaded_snapshot = foundation_repository.get_cluster_snapshot(snapshot["id"])
    listed_peer_runs = foundation_repository.list_peer_feature_runs(limit=10)

    assert loaded_snapshot["memberships"][0]["symbol"] == "1101"
    assert peer_run["warnings"] == ["2330 had no peers."]
    assert peer_run["overlays"][0]["detail"]["peer_symbols"] == ["1216"]
    assert listed_peer_runs[0]["id"] == peer_run["id"]


def test_ensure_default_failure_taxonomies_is_idempotent(monkeypatch):
    testing_session_local = _setup_session(
        monkeypatch,
        tables=[ExecutionFailureTaxonomy.__table__],
    )

    foundation_repository.ensure_default_failure_taxonomies()
    foundation_repository.ensure_default_failure_taxonomies()

    with testing_session_local() as session:
        rows = session.execute(select(ExecutionFailureTaxonomy)).scalars().all()

    assert sorted(row.code for row in rows) == [
        "kill_switch_active",
        "manual_confirmation_missing",
        "risk_check_failed",
        "sim_profile_missing",
    ]
