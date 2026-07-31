from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.research.repositories.runs as research_run_repository
import backend.research.services.run_projection as research_run_projection
from backend.database import (
    Base,
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)
from backend.research.domain.version_pack import build_version_pack_payload


def test_validation_parser_upgrades_legacy_empty_metrics_with_reason():
    payload = research_run_projection._validation_summary_from_payload(
        {"method": "walk_forward", "metrics": {}}
    )

    assert payload == {
        "method": "walk_forward",
        "evaluation_status": "not_evaluated",
        "status_reason": (
            "Legacy validation record has no metrics or persisted status reason."
        ),
        "metrics": {},
    }


def test_legacy_validation_remains_present_in_artifact_summary():
    validation = research_run_projection._validation_summary_from_payload(
        {"method": "walk_forward", "metrics": {}}
    )
    summary = research_run_projection._project_reviewable_payload(
        {
            "status": "succeeded",
            "comparison_eligibility": "research_only_comparable",
            "request_payload": {
                "validation": {
                    "method": "walk_forward",
                    "splits": 3,
                    "test_size": 0.2,
                },
                "baselines": [],
            },
            "validation": validation,
        },
        artifact_presence={
            "metrics": True,
            "model_diagnostics": True,
            "equity_curve": True,
            "signals": True,
            "validation": validation is not None,
            "baselines": False,
        },
        summary_only=False,
    )

    assert summary["artifact_completeness"] == "complete"
    assert "validation" in summary["present_artifacts"]
    assert "validation" not in summary["missing_artifacts"]


def test_requested_missing_baseline_remains_partial_after_reload():
    summary = research_run_projection._project_reviewable_payload(
        {
            "status": "succeeded",
            "comparison_eligibility": "research_only_comparable",
            "request_payload": {
                "validation": None,
                "baselines": ["buy_and_hold", "naive_momentum"],
            },
        },
        artifact_presence={
            "metrics": True,
            "model_diagnostics": True,
            "equity_curve": True,
            "signals": True,
            "validation": False,
            "baselines": False,
        },
        summary_only=False,
    )

    assert summary["artifact_completeness"] == "partial"
    assert "baselines" in summary["missing_artifacts"]
    assert "baselines" not in summary["present_artifacts"]


def test_model_diagnostics_parser_preserves_direction_diagnostics():
    payload = research_run_projection._model_diagnostics_from_payload(
        {
            "task": "regression",
            "sample_count": 2,
            "direction_classification": {
                "task": "binary_classification",
                "evaluation_status": "evaluated",
                "sample_count": 2,
                "positive_return_threshold": 0.0,
                "confirmation_probability_threshold": 0.5,
                "calibration_method": "sigmoid",
                "confirmation_policy_version": (
                    "regression_threshold_direction_probability_v1"
                ),
                "calibration_sample_count": 4,
                "positive_prevalence": 0.5,
                "confusion_matrix": [[1, 0], [0, 1]],
                "precision": 1.0,
                "recall": 1.0,
                "roc_auc": 1.0,
                "pr_auc": 1.0,
                "brier": 0.04,
            },
        }
    )

    assert payload["direction_classification"]["evaluation_status"] == "evaluated"
    assert payload["direction_classification"]["calibration_policy_version"] == (
        "chronological_tail_20pct_min20_class5_v1"
    )
    assert payload["direction_classification"]["confusion_matrix"] == [
        [1, 0],
        [0, 1],
    ]


def test_prospective_cohort_query_escapes_id_and_filters_false_positives(
    monkeypatch,
):
    cohort_id = "tw_2330_o2o_v1"
    exact_payload = research_run_repository.json_dumps(
        {
            "prospective_evidence": {
                "cohort_id": cohort_id,
            }
        }
    )
    false_positive_payload = research_run_repository.json_dumps(
        {
            "cohort_id": cohort_id,
            "prospective_evidence": {
                "cohort_id": "tw_all_active_o2o_v1",
            },
        }
    )
    exact_row = ResearchRun(
        run_id="exact",
        status="succeeded",
        request_payload_json=exact_payload,
    )
    statements = []

    class _CandidateResult:
        def all(self):
            return [
                ("exact", exact_payload),
                ("false-positive", false_positive_payload),
            ]

    class _RowResult:
        def scalars(self):
            return self

        def all(self):
            return [exact_row]

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            statements.append(statement)
            return _CandidateResult() if len(statements) == 1 else _RowResult()

    monkeypatch.setattr(research_run_repository, "SessionLocal", _Session)
    monkeypatch.setattr(
        research_run_repository,
        "_attach_liquidity_coverages",
        lambda session, payload: payload,
    )

    snapshots = research_run_repository.list_prospective_cohort_run_snapshots(
        cohort_id
    )

    assert [snapshot["run_id"] for snapshot in snapshots] == ["exact"]
    candidate_query = statements[0].compile()
    assert str(candidate_query).count("request_payload_json LIKE") == 2
    assert str(candidate_query).count("ESCAPE") == 2
    assert f'"{cohort_id.replace("_", "/_")}"' in candidate_query.params.values()
    assert statements[1].compile().params == {"run_id_1": ["exact"]}


def test_corrupt_baselines_json_is_not_marked_present():
    row = ResearchRun(
        run_id="corrupt-baselines",
        status="succeeded",
        request_payload_json=None,
        metrics_json="{}",
        model_diagnostics_json='{"task": "regression", "sample_count": 0}',
        equity_curve_json="[]",
        signals_json="[]",
        validation_outcome_json='{"method": "walk_forward", "metrics": {}}',
        baselines_json="{not-json",
        comparison_eligibility="research_only_comparable",
    )

    projected = research_run_projection.project_persisted_snapshot(
        research_run_repository._run_row_to_snapshot(row),
        include_artifacts=True,
    )

    assert projected["baselines"] == {}
    assert projected["artifact_completeness"] == "partial"
    assert "baselines" in projected["missing_artifacts"]
    assert "baselines" not in projected["present_artifacts"]


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
        "symbols": ["2330", "2317", "2454", "9999"],
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
        "request_payload": {
            "symbols": ["2330", "2317", "2454", "9999"],
            "direction_model": {"confirmation_probability_threshold": 0.5},
            "features": [
                {"name": "ma", "window": 5, "source": "close", "shift": 0}
            ],
        },
        "metrics": {
            "total_return": 0.12,
            "sharpe": 1.1,
            "max_drawdown": -0.08,
            "turnover": 0.3,
        },
        "equity_curve": [{"date": "2024-01-02", "equity": 1.0}],
        "signals": [
            {
                "date": datetime(2024, 1, 2, 12, 30, tzinfo=timezone.utc),
                "symbol": "2330",
                "score": 0.01,
                "position": 1.0,
                "signal_kind": "forward_opinion",
                "up_probability": 0.8,
                "predicted_direction": "up",
            },
            {
                "date": "2024-01-02", "symbol": "2317", "score": -0.02,
                "position": 0.0, "signal_kind": "forward_opinion",
                "up_probability": 0.2, "predicted_direction": "down",
            },
            {
                "date": "2024-01-02", "symbol": "2454", "score": 0.0,
                "position": 0.0, "signal_kind": "forward_opinion",
                "up_probability": 0.7, "predicted_direction": "up",
            },
            {
                "date": "2024-01-02", "symbol": "9999", "score": 0.02,
                "position": 0.0, "signal_kind": "forward_opinion",
                "up_probability": 0.8, "predicted_direction": "up",
            },
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
            "direction_classification": {
                "task": "binary_classification",
                "evaluation_status": "evaluated",
                "sample_count": 4,
            },
        },
        "warnings": [],
        "tradability_state": "research_only",
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
                "comparison_eligibility": "research_only_comparable",
                "investability_screening_active": False,
                "capacity_screening_version": "adv_ex_ante_buy_notional_0p5pct_v1",
                "adv_basis_version": "raw_close_x_volume_active_session_v1",
                "missing_feature_policy_version": "xgboost_native_missing_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)
    loaded = research_run_projection.get_research_run_record("run_123")

    assert loaded["run_id"] == "run_123"
    assert loaded["request_payload"]["features"][0]["shift"] == 0
    assert loaded["effective_strategy"] == {"threshold": 0.003, "top_n": 3}
    assert loaded["comparison_eligibility"] == "research_only_comparable"
    assert loaded["version_pack_status"]["adv_basis_version"] == "implemented"
    assert loaded["tradability_state"] == "research_only"
    assert loaded["tradability_contract_version"] == "p3_tradability_monitoring_v1"
    assert loaded["liquidity_bucket_coverages"][0]["bucket_key"] == "50m_to_200m"
    assert loaded["monitor_observation_status"] == "persisted"
    assert loaded["artifact_completeness"] == "complete"
    assert loaded["missing_artifacts"] == []
    assert loaded["not_required_artifacts"] == ["validation", "baselines"]
    assert loaded["opinion_artifact"]["state"] == "viable"
    assert [row["symbol"] for row in loaded["opinion_artifact"]["sell_or_avoid"]] == [
        "2317"
    ]
    assert [row["symbol"] for row in loaded["opinion_artifact"]["watch"]] == [
        "2454",
        "9999",
    ]
    opinion_row = loaded["opinion_artifact"]["buy_candidates"][0]
    assert opinion_row["symbol"] == "2330"
    assert opinion_row["model_score"] == 0.01
    assert opinion_row["position_signal"] == 1.0
    assert opinion_row["evidence_reason"]
    assert opinion_row["risk_or_warning"]
    assert opinion_row["invalidation_note"]
    assert {item["artifact"] for item in opinion_row["source_artifact_references"]} >= {
        "signals",
        "model_diagnostics",
        "metrics",
        "artifact_completeness",
        "comparison_caveats",
    }
    for reference in opinion_row["source_artifact_references"]:
        if reference["artifact"] == "signals":
            assert any(
                str(signal["symbol"]) == reference["symbol"]
                and str(signal["date"])[:10] == reference["date"]
                and reference["field"] in signal
                for signal in loaded["signals"]
            )
        else:
            assert reference["field"] in loaded
    checks = {
        item["check"]: item for item in loaded["opinion_artifact"]["review_checks"]
    }
    assert checks["strategy_lifecycle"]["status"] == "pass"
    assert checks["strategy_lifecycle"]["result"] == {
        "request_present": True,
        "effective_strategy_present": True,
        "diagnostics_present": True,
        "signals_present": True,
        "metrics_present": True,
        "opinion_rows_emitted_or_limited": True,
    }
    assert checks["signal_to_position"]["status"] == "pass"
    assert checks["signal_to_position"]["result"] == {
        "checked_symbol_count": 4,
        "positive_count": 1,
        "negative_count": 0,
        "flat_count": 3,
        "invalid_row_count": 0,
    }
    assert checks["backtest_report_discipline"]["status"] == "pass"
    assert checks["backtest_report_discipline"]["result"]["metric_keys"] == [
        "max_drawdown",
        "sharpe",
        "total_return",
        "turnover",
    ]
    assert checks["backtest_report_discipline"]["result"][
        "threshold_policy_version_present"
    ]
    assert checks["backtest_report_discipline"]["result"][
        "price_basis_version_present"
    ]
    assert checks["backtest_report_discipline"]["result"][
        "research_only_boundary_present"
    ]
    assert checks["robustness"]["status"] == "warning"
    assert checks["robustness"]["result"]["baseline_keys"] == []
    assert checks["parameter_sensitivity"]["status"] == "pass"
    assert checks["parameter_sensitivity"]["result"]["base_candidate_symbols"] == [
        "2330"
    ]
    assert checks["parameter_sensitivity"]["result"]["scenario_candidate_counts"] == {
        "strict_threshold": 2,
        "loose_threshold": 2,
        "top_n_minus_1": 2,
        "top_n_plus_1": 4,
    }
    assert checks["parameter_sensitivity"]["result"]["stable_symbols"] == ["2330"]
    assert checks["parameter_sensitivity"]["result"]["provisional_policy"]
    assert checks["source_artifact_audit"]["status"] == "warning"
    assert checks["source_artifact_audit"]["result"] == {
        "config_fallback_metadata_present": True,
        "config_sources_present": True,
        "fallback_audit_present": True,
        "raw_provider_parser_audit_available": False,
        "missing_raw_provider_parser_fields": [
            "provider_source_name",
            "parser_version",
            "fetch_status",
            "fetch_timestamp",
            "raw_ingest_audit_ref",
        ],
        "missing_config_fallback_inputs": [],
    }
    assert checks["text_evidence_summary"]["status"] == "not_evaluated"
    assert checks["text_evidence_summary"]["result"]["caveat_count"] == 0
    assert checks["text_evidence_summary"]["result"]["source_text_count"] == 0
    assert checks["text_evidence_summary"]["result"]["summary_text"] == ""
    assert all(item["source_artifact_references"] for item in checks.values())
    assert all(
        reference.get("symbol") == opinion_row["symbol"]
        for reference in opinion_row["source_artifact_references"]
        if reference["artifact"] == "signals" and "symbol" in reference
    )
    assert {
        reference["date"]
        for reference in opinion_row["source_artifact_references"]
        if reference["artifact"] == "signals" and "date" in reference
    } == {"2024-01-02"}


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

    loaded = research_run_projection.get_research_run_record("run_old")

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
    assert loaded["opinion_artifact"]["state"] == "no-opinion"
    assert loaded["opinion_artifact"]["buy_candidates"] == []
    assert loaded["opinion_artifact"]["sell_or_avoid"] == []
    assert loaded["opinion_artifact"]["watch"] == []
    assert loaded["opinion_artifact"]["evidence_limitations"]
    checks = {
        item["check"]: item for item in loaded["opinion_artifact"]["review_checks"]
    }
    assert checks["insufficient_evidence_gate"]["status"] == "pass"
    assert checks["robustness"]["status"] == "warning"
    assert checks["parameter_sensitivity"]["status"] == "not_evaluated"
    assert checks["source_artifact_audit"]["status"] == "not_evaluated"
    assert checks["text_evidence_summary"]["status"] == "warning"


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

    loaded = research_run_projection.get_research_run_record("run_partial")

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
    assert loaded["opinion_artifact"]["state"] == "no-opinion"
    assert loaded["opinion_artifact"]["evidence_limitations"]
    checks = {
        item["check"]: item for item in loaded["opinion_artifact"]["review_checks"]
    }
    assert checks["robustness"]["status"] == "warning"
    assert checks["parameter_sensitivity"]["status"] == "not_evaluated"
    assert checks["source_artifact_audit"]["status"] == "not_evaluated"


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

    loaded = research_run_projection.get_research_run_record("run_running")

    assert loaded["artifact_completeness"] == "metadata_only"
    assert {item["code"] for item in loaded["comparison_caveats"]} >= {
        "ARTIFACTS_NOT_EVALUATED",
        "METADATA_ONLY_RECORD",
    }
    assert loaded["opinion_artifact"]["state"] == "do-not-adopt"
    assert loaded["opinion_artifact"]["evidence_limitations"]


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
    listed = research_run_projection.list_research_run_records()

    assert listed[0]["run_id"] == "run_list"
    assert listed[0]["artifact_completeness"] == "complete"
    assert listed[0]["missing_artifacts"] == []
    assert listed[0]["equity_curve"] == []
    assert listed[0]["signals"] == []
    assert listed[0]["model_diagnostics"]["actual_vs_predicted"] == []
    assert listed[0]["opinion_artifact"]["state"] == "no-opinion"
    assert listed[0]["opinion_artifact"]["buy_candidates"] == []
    assert listed[0]["opinion_artifact"]["sell_or_avoid"] == []
    assert listed[0]["opinion_artifact"]["watch"] == []
    assert listed[0]["opinion_artifact"]["evidence_limitations"] == [
        "Detail artifacts are omitted; reload the run detail for row-level opinion review."
    ]
    listed_checks = {
        item["check"]: item for item in listed[0]["opinion_artifact"]["review_checks"]
    }
    assert listed_checks["signal_to_position"]["status"] == "not_evaluated"
    assert listed_checks["signal_to_position"]["result"] == {
        "omitted_for_summary": True
    }


def test_list_research_run_records_preserves_non_success_opinion_states(monkeypatch):
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
    statuses = ("running", "rejected", "validation_failed", "failed")

    with testing_session_local() as session:
        for status in statuses:
            row = ResearchRun(run_id=f"run_{status}")
            row.request_id = f"req_{status}"
            row.status = status
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

    listed_by_status = {
        item["status"]: item
        for item in research_run_projection.list_research_run_records()
    }

    assert set(listed_by_status) == set(statuses)
    for status in statuses:
        opinion = listed_by_status[status]["opinion_artifact"]
        assert opinion["state"] == "do-not-adopt"
        assert opinion["buy_candidates"] == []
        assert opinion["sell_or_avoid"] == []
        assert opinion["watch"] == []
        assert opinion["evidence_limitations"] == [
            f"Run status is {status}; artifacts are not adoptable.",
            "Detail artifacts are omitted; reload the run detail for row-level opinion review.",
        ]


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
