from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.micro_kpi_service as micro_kpi_service
import backend.services.research_gate_service as research_gate_service
from backend.database import (
    Base,
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)


def _session_local():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ResearchRun.__table__,
            ResearchRunLiquidityCoverage.__table__,
            MicrostructureObservation.__table__,
        ],
    )
    return testing_session_local


def _coverage(bucket_key: str, execution_coverage_ratio: float) -> dict[str, object]:
    return {
        "bucket_key": bucket_key,
        "bucket_label": bucket_key,
        "full_universe_count": 10,
        "execution_universe_count": int(10 * execution_coverage_ratio),
        "full_universe_ratio": 1.0,
        "execution_coverage_ratio": execution_coverage_ratio,
    }


def test_get_p3_phase_gate_summary_passes_with_complete_runs(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(research_gate_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        for index in range(20):
            run_id = f"run_{index}"
            session.add(
                ResearchRun(
                    run_id=run_id,
                    status="succeeded",
                    market="TW",
                    symbols_json='["2330"]',
                    tradability_state="execution_ready",
                    tradability_contract_version="p3_tradability_monitoring_v1",
                    investability_screening_active=False,
                    capacity_screening_active=False,
                    capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
                    missing_feature_policy_state="native_missing_supported",
                    corporate_event_state="clear",
                    full_universe_count=1,
                    execution_universe_count=1,
                    execution_universe_ratio=1.0,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    stale_mark_days_with_open_positions=0,
                    stale_risk_share=0.0,
                    created_at=datetime.now(timezone.utc) + timedelta(minutes=index),
                )
            )
            session.add(
                ResearchRunLiquidityCoverage(
                    run_id=run_id,
                    bucket_key="50m_to_200m",
                    bucket_label="50M-200M TWD",
                    full_universe_count=1,
                    execution_universe_count=1,
                    full_universe_ratio=1.0,
                    execution_coverage_ratio=1.0,
                )
            )
        session.commit()

    result = research_gate_service.get_p3_phase_gate_summary()

    assert result["gate_id"] == "GATE-P3-001"
    assert result["overall_status"] == "pass"
    assert result["metrics"]["KPI-RESEARCH-004"]["status"] == "pass"


def test_get_micro_kpi_summary_returns_bootstrap_only_when_baseline_short(
    monkeypatch,
):
    testing_session_local = _session_local()
    monkeypatch.setattr(micro_kpi_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        for index in range(30):
            session.add(
                MicrostructureObservation(
                    run_id=f"run_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 1, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=8,
                    execution_universe_ratio=0.8,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps(
                        [
                            {
                                "bucket_key": "50m_to_200m",
                                "bucket_label": "50M-200M TWD",
                                "full_universe_count": 10,
                                "execution_universe_count": 8,
                                "full_universe_ratio": 1.0,
                                "execution_coverage_ratio": 0.8,
                            }
                        ]
                    ),
                )
            )
        session.commit()

    result = micro_kpi_service.get_micro_kpi_summary()

    assert result["overall_status"] == "insufficient_sample"
    assert result["binding_status"] == "bootstrap_only"


def test_get_p3_phase_gate_summary_fails_when_latest_run_has_no_bucket_coverage(
    monkeypatch,
):
    testing_session_local = _session_local()
    monkeypatch.setattr(research_gate_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        historical_run = ResearchRun(
            run_id="run_historical",
            status="succeeded",
            market="TW",
            symbols_json='["2330"]',
            tradability_state="execution_ready",
            tradability_contract_version="p3_tradability_monitoring_v1",
            investability_screening_active=False,
            capacity_screening_active=False,
            capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
            missing_feature_policy_state="native_missing_supported",
            corporate_event_state="clear",
            full_universe_count=1,
            execution_universe_count=1,
            execution_universe_ratio=1.0,
            liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
            stale_mark_days_with_open_positions=0,
            stale_risk_share=0.0,
            created_at=datetime.now(timezone.utc),
        )
        latest_run = ResearchRun(
            run_id="run_latest",
            status="succeeded",
            market="TW",
            symbols_json='["2330"]',
            tradability_state="execution_ready",
            tradability_contract_version="p3_tradability_monitoring_v1",
            investability_screening_active=False,
            capacity_screening_active=False,
            capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
            missing_feature_policy_state="native_missing_supported",
            corporate_event_state="clear",
            full_universe_count=1,
            execution_universe_count=1,
            execution_universe_ratio=1.0,
            liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
            stale_mark_days_with_open_positions=0,
            stale_risk_share=0.0,
            created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        session.add_all([historical_run, latest_run])
        session.add(
            ResearchRunLiquidityCoverage(
                run_id="run_historical",
                bucket_key="50m_to_200m",
                bucket_label="50M-200M TWD",
                full_universe_count=1,
                execution_universe_count=1,
                full_universe_ratio=1.0,
                execution_coverage_ratio=1.0,
            )
        )
        session.commit()

    result = research_gate_service.get_p3_phase_gate_summary()

    artifact = result["artifacts"]["liquidity_and_capacity_labeling"]
    assert artifact["status"] == "fail"
    assert artifact["details"]["latest_run_id"] == "run_latest"
    assert artifact["details"]["latest_coverage_bucket_count"] == 0
    assert artifact["details"]["coverage_run_count"] == 1


def test_get_p3_phase_gate_summary_ignores_legacy_pre_p3_runs(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(research_gate_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        base_time = datetime.now(timezone.utc)
        for index in range(10):
            session.add(
                ResearchRun(
                    run_id=f"legacy_{index}",
                    status="succeeded",
                    market="TW",
                    symbols_json='["2330"]',
                    tradability_state="execution_ready",
                    investability_screening_active=False,
                    capacity_screening_active=False,
                    capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
                    missing_feature_policy_state="native_missing_supported",
                    corporate_event_state="clear",
                    full_universe_count=1,
                    execution_universe_count=1,
                    execution_universe_ratio=1.0,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    stale_mark_days_with_open_positions=0,
                    stale_risk_share=0.0,
                    created_at=base_time + timedelta(minutes=index),
                )
            )
        for index in range(20):
            run_id = f"p3_{index}"
            session.add(
                ResearchRun(
                    run_id=run_id,
                    status="succeeded",
                    market="TW",
                    symbols_json='["2330"]',
                    tradability_state="execution_ready",
                    tradability_contract_version="p3_tradability_monitoring_v1",
                    investability_screening_active=False,
                    capacity_screening_active=False,
                    capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
                    missing_feature_policy_state="native_missing_supported",
                    corporate_event_state="clear",
                    full_universe_count=1,
                    execution_universe_count=1,
                    execution_universe_ratio=1.0,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    stale_mark_days_with_open_positions=0,
                    stale_risk_share=0.0,
                    created_at=base_time + timedelta(hours=1, minutes=index),
                )
            )
            session.add(
                ResearchRunLiquidityCoverage(
                    run_id=run_id,
                    bucket_key="50m_to_200m",
                    bucket_label="50M-200M TWD",
                    full_universe_count=1,
                    execution_universe_count=1,
                    full_universe_ratio=1.0,
                    execution_coverage_ratio=1.0,
                )
            )
        session.commit()

    result = research_gate_service.get_p3_phase_gate_summary()

    metric = result["metrics"]["KPI-RESEARCH-004"]
    assert metric["status"] == "pass"
    assert metric["numerator"] == 20.0
    assert metric["denominator"] == 20.0


def test_get_p3_phase_gate_summary_filters_coverage_run_count_to_p3_runs(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(research_gate_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        session.add(
            ResearchRun(
                run_id="legacy_run",
                status="succeeded",
                market="TW",
                symbols_json='["2330"]',
                tradability_state="execution_ready",
                investability_screening_active=False,
                capacity_screening_active=False,
                capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
                missing_feature_policy_state="native_missing_supported",
                corporate_event_state="clear",
                full_universe_count=1,
                execution_universe_count=1,
                execution_universe_ratio=1.0,
                liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                stale_mark_days_with_open_positions=0,
                stale_risk_share=0.0,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            ResearchRunLiquidityCoverage(
                run_id="legacy_run",
                bucket_key="50m_to_200m",
                bucket_label="50M-200M TWD",
                full_universe_count=1,
                execution_universe_count=1,
                full_universe_ratio=1.0,
                execution_coverage_ratio=1.0,
            )
        )
        session.add(
            ResearchRun(
                run_id="p3_run",
                status="succeeded",
                market="TW",
                symbols_json='["2330"]',
                tradability_state="execution_ready",
                tradability_contract_version="p3_tradability_monitoring_v1",
                investability_screening_active=False,
                capacity_screening_active=False,
                capacity_screening_version="adv_ex_ante_buy_notional_0p5pct_v1",
                missing_feature_policy_state="native_missing_supported",
                corporate_event_state="clear",
                full_universe_count=1,
                execution_universe_count=1,
                execution_universe_ratio=1.0,
                liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                stale_mark_days_with_open_positions=0,
                stale_risk_share=0.0,
                created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
            )
        )
        session.add(
            ResearchRunLiquidityCoverage(
                run_id="p3_run",
                bucket_key="50m_to_200m",
                bucket_label="50M-200M TWD",
                full_universe_count=1,
                execution_universe_count=1,
                full_universe_ratio=1.0,
                execution_coverage_ratio=1.0,
            )
        )
        session.commit()

    result = research_gate_service.get_p3_phase_gate_summary()

    artifact = result["artifacts"]["liquidity_and_capacity_labeling"]
    assert artifact["details"]["latest_run_id"] == "p3_run"
    assert artifact["details"]["coverage_run_count"] == 1


def test_get_micro_kpi_summary_passes_with_stable_observations(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(micro_kpi_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        for index in range(80):
            session.add(
                MicrostructureObservation(
                    run_id=f"run_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 1, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=8,
                    execution_universe_ratio=0.8,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps(
                        [
                            {
                                "bucket_key": "50m_to_200m",
                                "bucket_label": "50M-200M TWD",
                                "full_universe_count": 10,
                                "execution_universe_count": 8,
                                "full_universe_ratio": 1.0,
                                "execution_coverage_ratio": 0.8,
                            }
                        ]
                    ),
                )
            )
        session.commit()

    result = micro_kpi_service.get_micro_kpi_summary()

    assert result["gate_id"] == "GATE-P3-OPS-001"
    assert result["overall_status"] == "pass"
    assert result["metrics"]["KPI-MICRO-001"]["status"] == "pass"
    assert result["metrics"]["KPI-MICRO-002"]["status"] == "pass"
    assert result["metrics"]["KPI-MICRO-003"]["status"] == "pass"


def test_get_micro_kpi_summary_reports_ratio_drift_formula(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(micro_kpi_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        for index in range(60):
            session.add(
                MicrostructureObservation(
                    run_id=f"baseline_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 1, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=8,
                    execution_universe_ratio=0.8,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps([_coverage("50m_to_200m", 0.8)]),
                )
            )
        for index in range(20):
            session.add(
                MicrostructureObservation(
                    run_id=f"active_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 3, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=6,
                    execution_universe_ratio=0.6,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps([_coverage("50m_to_200m", 0.8)]),
                )
            )
        session.commit()

    result = micro_kpi_service.get_micro_kpi_summary()

    metric = result["metrics"]["KPI-MICRO-001"]
    assert metric["status"] == "fail"
    assert metric["details"]["active_20d_avg"] == pytest.approx(0.6)
    assert metric["details"]["baseline_60d_avg"] == pytest.approx(0.8)
    assert metric["details"]["relative_drift"] == pytest.approx(0.25)


def test_get_micro_kpi_summary_uses_worst_bucket_drift(monkeypatch):
    testing_session_local = _session_local()
    monkeypatch.setattr(micro_kpi_service, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        for index in range(60):
            session.add(
                MicrostructureObservation(
                    run_id=f"baseline_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 1, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=8,
                    execution_universe_ratio=0.8,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps(
                        [
                            _coverage("10m_to_50m", 0.95),
                            _coverage("50m_to_200m", 0.8),
                        ]
                    ),
                )
            )
        for index in range(20):
            session.add(
                MicrostructureObservation(
                    run_id=f"active_{index}",
                    monitor_profile_id="p3_monitor_default_v1",
                    market="TW",
                    trading_date=date(2024, 3, 1) + timedelta(days=index),
                    full_universe_count=10,
                    execution_universe_count=8,
                    execution_universe_ratio=0.8,
                    stale_mark_with_open_positions=False,
                    liquidity_bucket_schema_version="liquidity_adv20_twd_bands_v1",
                    bucket_coverages_json=json.dumps(
                        [
                            _coverage("10m_to_50m", 0.93),
                            _coverage("50m_to_200m", 0.5),
                        ]
                    ),
                )
            )
        session.commit()

    result = micro_kpi_service.get_micro_kpi_summary()

    metric = result["metrics"]["KPI-MICRO-002"]
    assert metric["status"] == "fail"
    assert metric["value"] == pytest.approx(0.375)
    assert metric["details"]["required_buckets"]["10m_to_50m"]["drift"] < metric["value"]
    assert metric["details"]["required_buckets"]["50m_to_200m"]["drift"] == pytest.approx(metric["value"])
