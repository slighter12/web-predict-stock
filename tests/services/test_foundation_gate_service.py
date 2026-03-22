from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.foundation_gate_service as foundation_gate_service
from backend.database import (
    AdaptiveSurfaceExclusion,
    AdaptiveTrainingRun,
    Base,
    ClusterSnapshot,
    ExecutionFailureTaxonomy,
    ExecutionOrder,
    ExecutionOrderEvent,
    ExecutionPositionSnapshot,
    ExternalRawArchive,
    ExternalSignalAudit,
    FactorCatalog,
    FactorCatalogEntry,
    KillSwitchEvent,
    LiveRiskCheck,
    PeerFeatureRun,
    ResearchRun,
)


def _setup_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(foundation_gate_service, "SessionLocal", testing_session_local)
    return testing_session_local


def test_p9_gate_requires_order_history_and_readback_telemetry(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    submitted_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        session.add(
            ExecutionFailureTaxonomy(
                code="manual_confirmation_missing",
                route="simulation_internal_v1",
                description="manual confirmation missing",
                category="control",
            )
        )
        order = ExecutionOrder(
            run_id=None,
            route="simulation_internal_v1",
            market="TW",
            symbol="2330",
            side="buy",
            quantity=100.0,
            requested_price=100.0,
            status="filled",
            simulation_profile_id="sim_v1",
            live_control_profile_id=None,
            failure_code=None,
            manual_confirmation=True,
            rejection_reason=None,
            submitted_at=submitted_at,
            acknowledged_at=submitted_at,
        )
        session.add(order)
        session.flush()
        session.add_all(
            [
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="submitted",
                    event_ts=submitted_at,
                    detail_json="{}",
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="filled",
                    event_ts=submitted_at,
                    detail_json="{}",
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="position_readback",
                    event_ts=submitted_at,
                    detail_json="{}",
                ),
            ]
        )
        session.add(
            ExecutionPositionSnapshot(
                order_id=order.id,
                run_id=None,
                route="simulation_internal_v1",
                market="TW",
                symbol="2330",
                quantity=100.0,
                avg_price=100.0,
                snapshot_ts=submitted_at,
            )
        )
        session.commit()

    result = foundation_gate_service.get_p9_phase_gate_summary()

    assert result["overall_status"] == "fail"
    assert result["artifacts"]["order_history_persistence"]["status"] == "fail"
    assert result["artifacts"]["readback_telemetry_emission"]["status"] == "fail"


def test_p9_gate_passes_when_all_required_artifacts_exist(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    submitted_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        session.add(
            ExecutionFailureTaxonomy(
                code="risk_check_failed",
                route="simulation_internal_v1",
                description="risk check failed",
                category="risk",
            )
        )
        order = ExecutionOrder(
            run_id=None,
            route="simulation_internal_v1",
            market="TW",
            symbol="2330",
            side="buy",
            quantity=100.0,
            requested_price=100.0,
            status="filled",
            simulation_profile_id="sim_v1",
            live_control_profile_id=None,
            failure_code=None,
            manual_confirmation=True,
            rejection_reason=None,
            submitted_at=submitted_at,
            acknowledged_at=submitted_at,
        )
        session.add(order)
        session.flush()
        session.add_all(
            [
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="submitted",
                    event_ts=submitted_at,
                    detail_json='{"run_id":"run_1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="acknowledged",
                    event_ts=submitted_at,
                    detail_json='{"adapter_version":"simulation_internal_adapter_v1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="filled",
                    event_ts=submitted_at,
                    detail_json='{"route":"simulation_internal_v1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="position_readback",
                    event_ts=submitted_at,
                    detail_json='{"position_symbol":"2330"}',
                ),
            ]
        )
        session.add(
            ExecutionPositionSnapshot(
                order_id=order.id,
                run_id=None,
                route="simulation_internal_v1",
                market="TW",
                symbol="2330",
                quantity=100.0,
                avg_price=100.0,
                snapshot_ts=submitted_at,
            )
        )
        session.commit()

    result = foundation_gate_service.get_p9_phase_gate_summary()

    assert result["overall_status"] == "pass"
    assert result["artifacts"]["order_history_persistence"]["status"] == "pass"
    assert result["artifacts"]["readback_telemetry_emission"]["status"] == "pass"


def test_p11_gate_measures_surface_contamination_not_missing_exclusion_rows(
    monkeypatch,
):
    testing_session_local = _setup_session(monkeypatch)

    with testing_session_local() as session:
        session.add_all(
            [
                ResearchRun(
                    run_id="adaptive_excluded",
                    status="succeeded",
                    symbols_json="[]",
                    adaptive_mode="shadow",
                    adaptive_profile_id="adaptive_a",
                    adaptive_contract_version="adaptive_contract_v1",
                    reward_definition_version="reward_v1",
                    state_definition_version="state_v1",
                    rollout_control_version="rollout_v1",
                    comparison_eligibility="comparison_metadata_only",
                    tradability_state="research_only",
                ),
                ResearchRun(
                    run_id="adaptive_quarantined",
                    status="succeeded",
                    symbols_json="[]",
                    adaptive_mode="shadow",
                    adaptive_profile_id="adaptive_b",
                    adaptive_contract_version="adaptive_contract_v1",
                    reward_definition_version="reward_v1",
                    state_definition_version="state_v1",
                    rollout_control_version="rollout_v1",
                    comparison_eligibility="unresolved_event_quarantine",
                    tradability_state="research_only",
                ),
                ResearchRun(
                    run_id="adaptive_execution_ready",
                    status="succeeded",
                    symbols_json="[]",
                    adaptive_mode="shadow",
                    adaptive_profile_id="adaptive_c",
                    adaptive_contract_version="adaptive_contract_v1",
                    reward_definition_version="reward_v1",
                    state_definition_version="state_v1",
                    rollout_control_version="rollout_v1",
                    comparison_eligibility="comparison_metadata_only",
                    tradability_state="execution_ready",
                ),
                AdaptiveSurfaceExclusion(
                    run_id="adaptive_excluded",
                    exclusion_surface="default_non_adaptive_surfaces",
                    reason="isolated",
                ),
                AdaptiveTrainingRun(
                    profile_id=None,
                    run_id="adaptive_excluded",
                    market="TW",
                    adaptive_mode="shadow",
                    reward_definition_version="reward_v1",
                    state_definition_version="state_v1",
                    rollout_control_version="rollout_v1",
                    status="validated",
                    dataset_summary_json="{}",
                    artifact_registry_json="{}",
                    validation_error=None,
                ),
            ]
        )
        session.commit()

    result = foundation_gate_service.get_p11_phase_gate_summary()

    assert result["metrics"]["KPI-ADAPT-002"]["numerator"] == 1.0
    assert result["metrics"]["KPI-ADAPT-002"]["denominator"] == 3.0
    assert result["metrics"]["KPI-ADAPT-002"]["value"] == 1.0 / 3.0
    assert result["metrics"]["KPI-ADAPT-002"]["status"] == "fail"
    assert result["overall_status"] == "fail"


def test_p8_gate_requires_run_level_alignment_and_reporting(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    created_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        snapshot = ClusterSnapshot(
            snapshot_version="peer_cluster_kmeans_v1",
            run_id=None,
            factor_catalog_version="factor_v1",
            market="TW",
            trading_date=datetime(2026, 3, 20, tzinfo=timezone.utc).date(),
            cluster_count=2,
            symbol_count=10,
            status="succeeded",
            notes=None,
        )
        session.add(snapshot)
        session.flush()
        session.add(
            PeerFeatureRun(
                run_id=None,
                snapshot_id=snapshot.id,
                peer_policy_version="peer_relative_overlay_v1",
                market="TW",
                trading_date=snapshot.trading_date,
                status="succeeded",
                produced_feature_count=10,
                warning_count=0,
                warning_json="[]",
            )
        )
        session.add(
            ResearchRun(
                run_id="peer_enabled_run",
                status="succeeded",
                symbols_json='["2330"]',
                cluster_snapshot_version="peer_cluster_kmeans_v1",
                peer_policy_version="peer_relative_overlay_v1",
                peer_comparison_policy_version="peer_relative_overlay_v1",
                threshold_policy_version="threshold_v1",
                price_basis_version="price_basis_v1",
                comparison_eligibility="comparison_metadata_only",
                metrics_json='{"turnover":0.3}',
                created_at=created_at,
            )
        )
        session.commit()

    result = foundation_gate_service.get_p8_phase_gate_summary()

    assert result["artifacts"]["point_in_time_cluster_snapshots"]["status"] == "pass"
    assert result["artifacts"]["peer_features"]["status"] == "pass"
    assert result["metrics"]["KPI-RESEARCH-002"]["status"] == "pass"
    assert result["metrics"]["KPI-RESEARCH-003"]["status"] == "fail"
    assert result["overall_status"] == "fail"


def test_p8_gate_passes_with_turnover_and_concentration_reporting(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    created_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        snapshot = ClusterSnapshot(
            snapshot_version="peer_cluster_kmeans_v1",
            run_id=None,
            factor_catalog_version="factor_v1",
            market="TW",
            trading_date=datetime(2026, 3, 20, tzinfo=timezone.utc).date(),
            cluster_count=2,
            symbol_count=10,
            status="succeeded",
            notes=None,
        )
        session.add(snapshot)
        session.flush()
        session.add(
            PeerFeatureRun(
                run_id=None,
                snapshot_id=snapshot.id,
                peer_policy_version="peer_relative_overlay_v1",
                market="TW",
                trading_date=snapshot.trading_date,
                status="succeeded",
                produced_feature_count=10,
                warning_count=0,
                warning_json="[]",
            )
        )
        session.add(
            ResearchRun(
                run_id="peer_enabled_reported_run",
                status="succeeded",
                symbols_json='["2330"]',
                cluster_snapshot_version="peer_cluster_kmeans_v1",
                peer_policy_version="peer_relative_overlay_v1",
                peer_comparison_policy_version="peer_relative_overlay_v1",
                threshold_policy_version="threshold_v1",
                price_basis_version="price_basis_v1",
                comparison_eligibility="comparison_metadata_only",
                metrics_json='{"turnover":0.3,"max_position_weight":0.5}',
                created_at=created_at,
            )
        )
        session.commit()

    result = foundation_gate_service.get_p8_phase_gate_summary()

    assert result["metrics"]["KPI-RESEARCH-002"]["status"] == "pass"
    assert result["metrics"]["KPI-RESEARCH-003"]["status"] == "pass"
    assert result["overall_status"] == "pass"


def test_p10_gate_requires_kill_switch_and_broker_order_logging(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    submitted_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        order = ExecutionOrder(
            run_id=None,
            route="live_stub_v1",
            market="TW",
            symbol="2330",
            side="buy",
            quantity=100.0,
            requested_price=100.0,
            status="accepted_for_stub_dispatch",
            simulation_profile_id=None,
            live_control_profile_id="live_v1",
            failure_code=None,
            manual_confirmation=True,
            rejection_reason=None,
            submitted_at=submitted_at,
            acknowledged_at=submitted_at,
        )
        session.add(order)
        session.flush()
        session.add(
            LiveRiskCheck(
                order_id=order.id,
                status="pass",
                detail_json='{"gate":"risk_checks"}',
                checked_at=submitted_at,
            )
        )
        session.commit()

    result = foundation_gate_service.get_p10_phase_gate_summary()

    assert result["metrics"]["KPI-LIVE-001"]["status"] == "pass"
    assert result["metrics"]["KPI-LIVE-002"]["status"] == "pass"
    assert result["metrics"]["KPI-LIVE-003"]["status"] == "pass"
    assert result["metrics"]["KPI-LIVE-003"]["value"] == 0.0
    assert result["artifacts"]["kill_switch"]["status"] == "fail"
    assert result["artifacts"]["broker_order_logging"]["status"] == "fail"
    assert result["overall_status"] == "fail"


def test_p11_gate_requires_isolated_adaptive_workflow_artifact(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)

    with testing_session_local() as session:
        session.add(
            ResearchRun(
                run_id="adaptive_quarantined",
                status="succeeded",
                symbols_json="[]",
                adaptive_mode="shadow",
                adaptive_profile_id="adaptive_a",
                adaptive_contract_version="adaptive_contract_v1",
                reward_definition_version="reward_v1",
                state_definition_version="state_v1",
                rollout_control_version="rollout_v1",
                comparison_eligibility="unresolved_event_quarantine",
                tradability_state="research_only",
            )
        )
        session.commit()

    result = foundation_gate_service.get_p11_phase_gate_summary()

    assert result["metrics"]["KPI-ADAPT-001"]["status"] == "pass"
    assert result["metrics"]["KPI-ADAPT-002"]["status"] == "pass"
    assert result["metrics"]["KPI-ADAPT-003"]["status"] == "pass"
    assert result["artifacts"]["isolated_adaptive_workflow"]["status"] == "fail"
    assert result["overall_status"] == "fail"


def test_p10_gate_passes_when_all_required_artifacts_exist(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)
    submitted_at = datetime(2026, 3, 21, 1, 0, tzinfo=timezone.utc)

    with testing_session_local() as session:
        order = ExecutionOrder(
            run_id=None,
            route="live_stub_v1",
            market="TW",
            symbol="2330",
            side="buy",
            quantity=100.0,
            requested_price=100.0,
            status="accepted_for_stub_dispatch",
            simulation_profile_id=None,
            live_control_profile_id="live_v1",
            failure_code=None,
            manual_confirmation=True,
            rejection_reason=None,
            submitted_at=submitted_at,
            acknowledged_at=submitted_at,
        )
        session.add(order)
        session.flush()
        session.add_all(
            [
                LiveRiskCheck(
                    order_id=order.id,
                    status="pass",
                    detail_json='{"gate":"risk_checks"}',
                    checked_at=submitted_at,
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="submitted",
                    event_ts=submitted_at,
                    detail_json='{"route":"live_stub_v1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="acknowledged",
                    event_ts=submitted_at,
                    detail_json='{"route":"live_stub_v1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="filled",
                    event_ts=submitted_at,
                    detail_json='{"route":"live_stub_v1"}',
                ),
                ExecutionOrderEvent(
                    order_id=order.id,
                    event_type="position_readback",
                    event_ts=submitted_at,
                    detail_json='{"route":"live_stub_v1"}',
                ),
                KillSwitchEvent(
                    scope_type="global",
                    market=None,
                    is_enabled=False,
                    reason="control installed",
                ),
            ]
        )
        session.commit()

    result = foundation_gate_service.get_p10_phase_gate_summary()

    assert result["artifacts"]["kill_switch"]["status"] == "pass"
    assert result["artifacts"]["broker_order_logging"]["status"] == "pass"
    assert result["overall_status"] == "pass"


def test_p7_gate_requires_timing_mapping_artifact(monkeypatch):
    testing_session_local = _setup_session(monkeypatch)

    with testing_session_local() as session:
        session.add(
            ExternalRawArchive(
                source_family="tw_company_event_layer_v1",
                market="TW",
                coverage_start=datetime(2026, 3, 1, tzinfo=timezone.utc).date(),
                coverage_end=datetime(2026, 3, 20, tzinfo=timezone.utc).date(),
                record_count=10,
                payload_body="{}",
                notes=None,
            )
        )
        session.add(
            FactorCatalog(
                id="catalog_v1",
                market="TW",
                source_family="tw_company_event_layer_v1",
                lineage_version="lineage_v1",
                minimum_coverage_ratio=0.8,
                is_active=True,
                notes=None,
            )
        )
        session.add(
            FactorCatalogEntry(
                catalog_id="catalog_v1",
                factor_id="important_event_count_30d_v1",
                display_name="Important Event Count 30d",
                formula_definition="count(events)",
                lineage="lineage_v1",
                timing_semantics="official_publication_ts_pti",
                missing_value_policy="zero_when_no_events",
                scoring_eligible=True,
            )
        )
        session.add(
            ExternalSignalAudit(
                source_family="tw_company_event_layer_v1",
                market="TW",
                audit_window_start=datetime(2026, 3, 1, tzinfo=timezone.utc).date(),
                audit_window_end=datetime(2026, 3, 20, tzinfo=timezone.utc).date(),
                sample_size=10,
                fallback_sample_size=2,
                undocumented_count=0,
                draw_rule_version="deterministic_external_signal_audit_v1",
                result_json='{"sample_record_ids":[1,2,3]}',
            )
        )
        session.commit()

    result = foundation_gate_service.get_p7_phase_gate_summary()

    assert result["artifacts"]["timing_mapping"]["status"] == "fail"
    assert result["overall_status"] == "fail"
