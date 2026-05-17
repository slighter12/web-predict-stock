from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.research.repositories.runs as research_run_repository
from backend.database import (
    Base,
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)
from backend.research.domain.version_pack import build_version_pack_payload


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
        "equity_curve": [{"date": "2024-01-02", "equity": 1.0}],
        "signals": [
            {"date": "2024-01-02", "symbol": "2330", "score": 0.01, "position": 1.0}
        ],
        "model_diagnostics": {
            "task": "regression",
            "sample_count": 2,
            "rmse": 0.1,
            "mae": 0.08,
            "rank_ic": 0.2,
            "linear_ic": 0.1,
            "actual_vs_predicted": [],
            "residuals": [],
            "feature_importance": [],
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
    assert loaded["artifact_completeness"] == "complete"
    assert loaded["missing_artifacts"] == []
    assert loaded["not_required_artifacts"] == ["validation", "baselines"]


def test_research_run_repository_classifies_metadata_only_old_row(monkeypatch):
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

    with testing_session_local() as session:
        row = ResearchRun(run_id="run_old")
        row.request_id = "req_old"
        row.status = "succeeded"
        row.market = "TW"
        row.symbols_json = '["2330"]'
        row.strategy_type = "research_v1"
        row.request_payload_json = research_run_repository.json_dumps(
            {"symbols": ["2330"], "baselines": []}
        )
        row.comparison_eligibility = "comparison_metadata_only"
        row.warnings_json = "[]"
        session.add(row)
        session.commit()

    loaded = research_run_repository.get_research_run_record("run_old")

    assert loaded["artifact_completeness"] == "metadata_only"
    assert loaded["present_artifacts"] == []
    assert loaded["missing_artifacts"] == [
        "metrics",
        "model_diagnostics",
        "equity_curve",
        "signals",
    ]
    assert loaded["not_required_artifacts"] == ["validation", "baselines"]
    assert {item["code"] for item in loaded["comparison_caveats"]} >= {
        "METADATA_ONLY_RECORD",
        "COMPARISON_METADATA_ONLY",
    }


def test_research_run_repository_classifies_partial_artifacts(monkeypatch):
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

    with testing_session_local() as session:
        row = ResearchRun(run_id="run_partial")
        row.request_id = "req_partial"
        row.status = "succeeded"
        row.market = "TW"
        row.symbols_json = '["2330"]'
        row.strategy_type = "research_v1"
        row.request_payload_json = research_run_repository.json_dumps(
            {"symbols": ["2330"], "baselines": []}
        )
        row.metrics_json = research_run_repository.json_dumps(
            {
                "total_return": 0.12,
                "sharpe": 1.1,
                "max_drawdown": -0.08,
                "turnover": 0.3,
            }
        )
        row.comparison_eligibility = "research_only_comparable"
        row.warnings_json = "[]"
        session.add(row)
        session.commit()

    loaded = research_run_repository.get_research_run_record("run_partial")

    assert loaded["artifact_completeness"] == "partial"
    assert loaded["present_artifacts"] == ["metrics"]
    assert loaded["missing_artifacts"] == [
        "model_diagnostics",
        "equity_curve",
        "signals",
    ]
    assert {item["code"] for item in loaded["comparison_caveats"]} == {
        "REVIEW_ARTIFACTS_MISSING"
    }


def test_research_run_repository_marks_running_artifacts_not_evaluated(monkeypatch):
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

    with testing_session_local() as session:
        row = ResearchRun(run_id="run_running")
        row.request_id = "req_running"
        row.status = "running"
        row.market = "TW"
        row.symbols_json = '["2330"]'
        row.strategy_type = "research_v1"
        row.request_payload_json = research_run_repository.json_dumps(
            {"symbols": ["2330"], "baselines": []}
        )
        row.comparison_eligibility = "comparison_metadata_only"
        row.warnings_json = "[]"
        session.add(row)
        session.commit()

    loaded = research_run_repository.get_research_run_record("run_running")

    assert loaded["artifact_completeness"] == "metadata_only"
    assert {item["code"] for item in loaded["comparison_caveats"]} >= {
        "ARTIFACTS_NOT_EVALUATED",
        "METADATA_ONLY_RECORD",
    }


def test_list_research_run_records_keeps_summary_without_heavy_artifacts(monkeypatch):
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
        "run_id": "run_list",
        "request_id": "req_list",
        "status": "succeeded",
        "market": "TW",
        "symbols": ["2330"],
        "strategy_type": "research_v1",
        "request_payload": {"symbols": ["2330"], "baselines": []},
        "metrics": {
            "total_return": 0.12,
            "sharpe": 1.1,
            "max_drawdown": -0.08,
            "turnover": 0.3,
        },
        "equity_curve": [{"date": "2024-01-02", "equity": 1.0}],
        "signals": [
            {"date": "2024-01-02", "symbol": "2330", "score": 0.01, "position": 1.0}
        ],
        "model_diagnostics": {
            "task": "regression",
            "sample_count": 2,
            "rmse": 0.1,
            "mae": 0.08,
            "rank_ic": 0.2,
            "linear_ic": 0.1,
            "actual_vs_predicted": [],
            "residuals": [],
            "feature_importance": [],
        },
        "warnings": [],
        "comparison_eligibility": "research_only_comparable",
    }

    research_run_repository.persist_research_run_record(payload)
    listed = research_run_repository.list_research_run_records()

    assert listed[0]["run_id"] == "run_list"
    assert listed[0]["artifact_completeness"] == "complete"
    assert listed[0]["missing_artifacts"] == []
    assert listed[0]["equity_curve"] == []
    assert listed[0]["signals"] == []
    assert listed[0]["model_diagnostics"]["actual_vs_predicted"] == []


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
