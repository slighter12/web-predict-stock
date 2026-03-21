from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.repositories.research_run_repository as research_run_repository
from backend.database import (
    Base,
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)
from backend.domain.runtime_bundle import build_version_pack_payload


def test_research_run_repository_roundtrip(monkeypatch):
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
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    payload = {
        "run_id": "run_123",
        "request_id": "req_123",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["2330"],
        "strategy_type": "research_v1",
        "runtime_mode": "runtime_compatibility_mode",
        "default_bundle_version": None,
        "effective_strategy": {"threshold": 0.003, "top_n": 3},
        "allow_proactive_sells": True,
        "config_sources": {
            "strategy": {"threshold": "request_override", "top_n": "request_override"}
        },
        "fallback_audit": {
            "strategy": {
                "threshold": {"attempted": False, "outcome": "not_needed"},
                "top_n": {"attempted": False, "outcome": "not_needed"},
            }
        },
        "validation_outcome": {"ok": True},
        "rejection_reason": None,
        "request_payload": {"symbols": ["2330"]},
        "metrics": {
            "total_return": 0.12,
            "sharpe": 1.1,
            "max_drawdown": -0.08,
            "turnover": 0.3,
        },
        "warnings": [],
        "tradability_state": "execution_ready",
        "tradability_contract_version": "p3_tradability_monitoring_v1",
        "capacity_screening_active": False,
        "missing_feature_policy_state": "native_missing_supported",
        "corporate_event_state": "clear",
        "full_universe_count": 1,
        "execution_universe_count": 1,
        "execution_universe_ratio": 1.0,
        "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
        "liquidity_bucket_coverages": [
            {
                "bucket_key": "50m_to_200m",
                "bucket_label": "50M-200M TWD",
                "full_universe_count": 1,
                "execution_universe_count": 1,
                "full_universe_ratio": 1.0,
                "execution_coverage_ratio": 1.0,
            }
        ],
        "stale_mark_days_with_open_positions": 0,
        "stale_risk_share": 0.0,
        "monitor_profile_id": "p3_monitor_default_v1",
        "monitor_observation_status": "persisted",
        "microstructure_observations": [
            {
                "monitor_profile_id": "p3_monitor_default_v1",
                "market": "TW",
                "trading_date": "2024-01-02",
                "full_universe_count": 1,
                "execution_universe_count": 1,
                "execution_universe_ratio": 1.0,
                "stale_mark_with_open_positions": False,
                "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                "bucket_coverages": [
                    {
                        "bucket_key": "50m_to_200m",
                        "bucket_label": "50M-200M TWD",
                        "full_universe_count": 1,
                        "execution_universe_count": 1,
                        "full_universe_ratio": 1.0,
                        "execution_coverage_ratio": 1.0,
                    }
                ],
            }
        ],
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
                "investability_screening_active": False,
                "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
                "adv_basis_version": "raw_close_x_volume_active_session_v1",
                "missing_feature_policy_version": "xgboost_native_missing_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)
    loaded = research_run_repository.get_research_run_record("run_123")

    assert loaded["run_id"] == "run_123"
    assert loaded["effective_strategy"] == {"threshold": 0.003, "top_n": 3}
    assert loaded["comparison_eligibility"] == "comparison_metadata_only"
    assert loaded["version_pack_status"]["adv_basis_version"] == "implemented"
    assert loaded["tradability_contract_version"] == "p3_tradability_monitoring_v1"
    assert loaded["liquidity_bucket_coverages"][0]["bucket_key"] == "50m_to_200m"
    assert loaded["monitor_observation_status"] == "persisted"


def test_research_run_repository_reassigns_existing_observation_run_id(monkeypatch):
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
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    base_payload = {
        "request_id": "req_123",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["2330"],
        "strategy_type": "research_v1",
        "runtime_mode": "runtime_compatibility_mode",
        "default_bundle_version": None,
        "effective_strategy": {"threshold": 0.003, "top_n": 3},
        "allow_proactive_sells": True,
        "config_sources": {
            "strategy": {"threshold": "request_override", "top_n": "request_override"}
        },
        "fallback_audit": {
            "strategy": {
                "threshold": {"attempted": False, "outcome": "not_needed"},
                "top_n": {"attempted": False, "outcome": "not_needed"},
            }
        },
        "validation_outcome": {"ok": True},
        "rejection_reason": None,
        "request_payload": {"symbols": ["2330"]},
        "metrics": {
            "total_return": 0.12,
            "sharpe": 1.1,
            "max_drawdown": -0.08,
            "turnover": 0.3,
        },
        "warnings": [],
        "tradability_state": "execution_ready",
        "tradability_contract_version": "p3_tradability_monitoring_v1",
        "capacity_screening_active": False,
        "missing_feature_policy_state": "native_missing_supported",
        "corporate_event_state": "clear",
        "full_universe_count": 1,
        "execution_universe_count": 1,
        "execution_universe_ratio": 1.0,
        "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
        "liquidity_bucket_coverages": [],
        "stale_mark_days_with_open_positions": 0,
        "stale_risk_share": 0.0,
        "monitor_profile_id": "p3_monitor_default_v1",
        "monitor_observation_status": "persisted",
        "microstructure_observations": [
            {
                "monitor_profile_id": "p3_monitor_default_v1",
                "market": "TW",
                "trading_date": "2024-01-02",
                "full_universe_count": 1,
                "execution_universe_count": 1,
                "execution_universe_ratio": 1.0,
                "stale_mark_with_open_positions": False,
                "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                "bucket_coverages": [],
            }
        ],
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
                "investability_screening_active": False,
                "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
                "adv_basis_version": "raw_close_x_volume_active_session_v1",
                "missing_feature_policy_version": "xgboost_native_missing_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(
        {
            **base_payload,
            "run_id": "run_old",
        }
    )
    research_run_repository.persist_research_run_record(
        {
            **base_payload,
            "run_id": "run_new",
        }
    )

    with testing_session_local() as session:
        observation = session.query(MicrostructureObservation).one()

    assert observation.run_id == "run_new"


def test_research_run_repository_prunes_stale_monitor_observations(monkeypatch):
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
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    base_payload = {
        "request_id": "req_123",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["2330"],
        "strategy_type": "research_v1",
        "runtime_mode": "runtime_compatibility_mode",
        "default_bundle_version": None,
        "effective_strategy": {"threshold": 0.003, "top_n": 3},
        "allow_proactive_sells": True,
        "config_sources": None,
        "fallback_audit": None,
        "validation_outcome": {"ok": True},
        "rejection_reason": None,
        "request_payload": {"symbols": ["2330"]},
        "metrics": None,
        "warnings": [],
        "tradability_state": "execution_ready",
        "tradability_contract_version": "p3_tradability_monitoring_v1",
        "capacity_screening_active": True,
        "missing_feature_policy_state": "native_missing_supported",
        "corporate_event_state": "clear",
        "full_universe_count": 1,
        "execution_universe_count": 1,
        "execution_universe_ratio": 1.0,
        "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
        "liquidity_bucket_coverages": [],
        "stale_mark_days_with_open_positions": 0,
        "stale_risk_share": 0.0,
        "monitor_profile_id": "p3_monitor_default_v1",
        "monitor_observation_status": "persisted",
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
                "investability_screening_active": False,
                "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
                "adv_basis_version": "raw_close_x_volume_active_session_v1",
                "missing_feature_policy_version": "xgboost_native_missing_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(
        {
            **base_payload,
            "run_id": "run_old",
            "microstructure_observations": [
                {
                    "monitor_profile_id": "p3_monitor_default_v1",
                    "market": "TW",
                    "trading_date": "2024-01-02",
                    "full_universe_count": 1,
                    "execution_universe_count": 1,
                    "execution_universe_ratio": 1.0,
                    "stale_mark_with_open_positions": False,
                    "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                    "bucket_coverages": [],
                },
                {
                    "monitor_profile_id": "p3_monitor_default_v1",
                    "market": "TW",
                    "trading_date": "2024-01-03",
                    "full_universe_count": 1,
                    "execution_universe_count": 1,
                    "execution_universe_ratio": 1.0,
                    "stale_mark_with_open_positions": False,
                    "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                    "bucket_coverages": [],
                },
            ],
        }
    )
    research_run_repository.persist_research_run_record(
        {
            **base_payload,
            "run_id": "run_new",
            "microstructure_observations": [
                {
                    "monitor_profile_id": "p3_monitor_default_v1",
                    "market": "TW",
                    "trading_date": "2024-01-03",
                    "full_universe_count": 1,
                    "execution_universe_count": 1,
                    "execution_universe_ratio": 1.0,
                    "stale_mark_with_open_positions": False,
                    "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                    "bucket_coverages": [],
                }
            ],
        }
    )

    with testing_session_local() as session:
        observations = (
            session.query(MicrostructureObservation)
            .order_by(MicrostructureObservation.trading_date.asc())
            .all()
        )

    assert len(observations) == 1
    assert observations[0].run_id == "run_new"
    assert observations[0].trading_date.isoformat() == "2024-01-03"


def test_research_run_repository_accepts_datetime_observation_dates(monkeypatch):
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
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    payload = {
        "run_id": "run_datetime",
        "request_id": "req_123",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["2330"],
        "strategy_type": "research_v1",
        "runtime_mode": "runtime_compatibility_mode",
        "default_bundle_version": None,
        "effective_strategy": {"threshold": 0.003, "top_n": 3},
        "allow_proactive_sells": True,
        "config_sources": None,
        "fallback_audit": None,
        "validation_outcome": {"ok": True},
        "rejection_reason": None,
        "request_payload": {"symbols": ["2330"]},
        "metrics": None,
        "warnings": [],
        "tradability_state": "execution_ready",
        "tradability_contract_version": "p3_tradability_monitoring_v1",
        "capacity_screening_active": True,
        "missing_feature_policy_state": "native_missing_supported",
        "corporate_event_state": "clear",
        "full_universe_count": 1,
        "execution_universe_count": 1,
        "execution_universe_ratio": 1.0,
        "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
        "liquidity_bucket_coverages": [],
        "stale_mark_days_with_open_positions": 0,
        "stale_risk_share": 0.0,
        "monitor_profile_id": "p3_monitor_default_v1",
        "monitor_observation_status": "persisted",
        "microstructure_observations": [
            {
                "monitor_profile_id": "p3_monitor_default_v1",
                "market": "TW",
                "trading_date": datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc),
                "full_universe_count": 1,
                "execution_universe_count": 1,
                "execution_universe_ratio": 1.0,
                "stale_mark_with_open_positions": False,
                "liquidity_bucket_schema_version": "liquidity_adv20_twd_bands_v1",
                "bucket_coverages": [],
            }
        ],
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
                "investability_screening_active": False,
                "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
                "adv_basis_version": "raw_close_x_volume_active_session_v1",
                "missing_feature_policy_version": "xgboost_native_missing_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)

    with testing_session_local() as session:
        observation = session.query(MicrostructureObservation).one()

    assert observation.trading_date.isoformat() == "2024-01-02"
