import copy
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import backend.research.repositories.runs as research_run_repository
import backend.research.services.run_projection as research_run_projection
from backend.database import (
    Base,
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
)
from backend.research.contracts.runs import ResearchRunRecordResponse
from backend.research.domain.version_pack import build_version_pack_payload
from backend.research.domain.result_caveats import (
    DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE,
    DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_MESSAGE,
    INVALID_DYNAMIC_EFFECTIVE_STRATEGY_METADATA,
    TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE,
    TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
)


_VALID_DYNAMIC_POLICY = {
    "policy_version": "dynamic_threshold_v1",
    "return_target": "open_to_open",
    "horizon_days": 5,
    "lookback": 20,
    "multiplier": 1.5,
    "estimator": "sample_standard_deviation",
    "ddof": 1,
    "complete_window_required": True,
    "continuity_policy_version": "market_date_continuity_v1",
    "horizon_scaling": "square_root",
}


def _dynamic_strategy_snapshot(
    strategy: dict,
    *,
    effective_top_n: int | None = None,
    comparison_eligibility: str = "research_only_comparable",
) -> dict:
    row = ResearchRun(
        run_id="dynamic-projection",
        status="succeeded",
        market="US",
        effective_top_n=effective_top_n,
        request_payload_json=research_run_repository.json_dumps(
            {"market": "US", "strategy": strategy}
        ),
        comparison_eligibility=comparison_eligibility,
    )
    return research_run_repository._run_row_to_snapshot(row)


@pytest.mark.parametrize(
    ("strategy", "expected_field"),
    [
        (
            {
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": _VALID_DYNAMIC_POLICY,
            },
            "top_n",
        ),
        (
            {"threshold_mode": "dynamic", "top_n": 5},
            "dynamic_threshold_policy",
        ),
        (
            {
                "threshold_mode": "dynamic",
                "top_n": 5,
                "dynamic_threshold_policy": {
                    "policy_version": "secret-policy",
                    "lookback": 20,
                },
            },
            "dynamic_threshold_policy",
        ),
    ],
)
def test_invalid_dynamic_strategy_metadata_projects_safe_reloadable_record(
    strategy,
    expected_field,
    caplog,
):
    snapshot = _dynamic_strategy_snapshot(strategy)
    original_snapshot = copy.deepcopy(snapshot)

    with caplog.at_level(logging.WARNING, logger=research_run_projection.__name__):
        projected = research_run_projection.project_persisted_snapshot(
            snapshot,
            include_artifacts=True,
        )
        projected_again = research_run_projection.project_persisted_snapshot(
            snapshot,
            include_artifacts=True,
        )

    response = ResearchRunRecordResponse.model_validate(projected)

    assert response.effective_strategy is None
    assert response.comparison_eligibility == "comparison_metadata_only"
    assert (
        response.comparison_caveats[0].code
        == DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE
    )
    assert response.artifact_completeness == "metadata_only"
    assert response.warnings.count(INVALID_DYNAMIC_EFFECTIVE_STRATEGY_METADATA) == 1
    caveats = {
        item.code: item for item in response.comparison_caveats
    }
    assert caveats[DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE].severity == (
        "blocker"
    )
    assert (
        caveats[DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE].label
        == DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_MESSAGE
    )
    assert response.opinion_artifact.state == "no-opinion"
    assert DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_MESSAGE in (
        response.opinion_artifact.state_reason
    )
    assert projected_again["warnings"].count(
        INVALID_DYNAMIC_EFFECTIVE_STRATEGY_METADATA
    ) == 1
    assert snapshot == original_snapshot
    assert expected_field in caplog.text
    assert "secret-policy" not in caplog.text


def test_invalid_dynamic_strategy_metadata_preserves_stricter_comparison_state():
    snapshot = _dynamic_strategy_snapshot(
        {"threshold_mode": "dynamic", "top_n": 5},
        comparison_eligibility="unresolved_event_quarantine",
    )

    projected = research_run_projection.project_persisted_snapshot(
        snapshot,
        include_artifacts=True,
    )

    assert projected["comparison_eligibility"] == "unresolved_event_quarantine"
    assert any(
        item["code"] == DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE
        and item["severity"] == "blocker"
        for item in projected["comparison_caveats"]
    )


def test_dynamic_request_rejects_static_effective_strategy_metadata():
    projected = research_run_projection._project_reviewable_payload(
        {
            "run_id": "dynamic-static-mismatch",
            "status": "succeeded",
            "market": "US",
            "request_payload": {
                "strategy": {
                    "threshold_mode": "dynamic",
                    "top_n": 5,
                    "dynamic_threshold_policy": _VALID_DYNAMIC_POLICY,
                },
                "validation": None,
                "baselines": [],
            },
            "effective_strategy": {"threshold": 0.003, "top_n": 5},
            "comparison_eligibility": "research_only_comparable",
            "warnings": [],
        },
        artifact_presence={
            "metrics": True,
            "model_diagnostics": True,
            "equity_curve": True,
            "signals": True,
            "validation": True,
            "baselines": True,
        },
        summary_only=False,
    )

    assert projected["effective_strategy"] is None
    assert projected["comparison_eligibility"] == "comparison_metadata_only"
    assert projected["warnings"] == [INVALID_DYNAMIC_EFFECTIVE_STRATEGY_METADATA]
    assert (
        projected["comparison_caveats"][0]["code"]
        == DYNAMIC_STRATEGY_METADATA_UNAVAILABLE_CAVEAT_CODE
    )
    assert projected["opinion_artifact"]["state"] == "no-opinion"


def test_invalid_dynamic_strategy_metadata_keeps_complete_artifact_status():
    projected = research_run_projection._project_reviewable_payload(
        {
            "run_id": "dynamic-complete-artifacts",
            "status": "succeeded",
            "market": "US",
            "request_payload": {
                "strategy": {"threshold_mode": "dynamic", "top_n": 5},
                "validation": None,
                "baselines": [],
            },
            "effective_strategy": None,
            "comparison_eligibility": "research_only_comparable",
            "warnings": [],
        },
        artifact_presence={
            "metrics": True,
            "model_diagnostics": True,
            "equity_curve": True,
            "signals": True,
            "validation": True,
            "baselines": True,
        },
        summary_only=False,
    )

    assert projected["artifact_completeness"] == "complete"
    assert projected["comparison_eligibility"] == "comparison_metadata_only"
    assert projected["opinion_artifact"]["state"] == "no-opinion"


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


def test_failed_tw_projection_does_not_add_universe_caveat():
    projected = research_run_projection._project_reviewable_payload(
        {
            "status": "failed",
            "market": "TW",
            "comparison_eligibility": "comparison_metadata_only",
            "request_payload": {"market": "TW", "validation": None, "baselines": []},
        },
        artifact_presence={
            "metrics": False,
            "model_diagnostics": False,
            "equity_curve": False,
            "signals": False,
            "validation": False,
            "baselines": False,
        },
        summary_only=False,
    )

    assert TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE not in {
        item["code"] for item in projected["comparison_caveats"]
    }


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
        def yield_per(self, size):
            self.size = size
            return self

        def partitions(self, size):
            self.size = size
            return iter(
                [
                    [
                        ("exact", exact_payload),
                        ("false-positive", false_positive_payload),
                    ]
                ]
            )

    class _RowResult:
        def scalars(self):
            return self

        def all(self):
            return [exact_row]

    class _CoverageResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            statements.append(statement)
            if len(statements) == 1:
                return _CandidateResult()
            if len(statements) == 2:
                return _RowResult()
            return _CoverageResult()

    monkeypatch.setattr(research_run_repository, "SessionLocal", _Session)

    snapshots = research_run_repository.list_prospective_cohort_run_snapshots(
        cohort_id
    )

    assert [snapshot["run_id"] for snapshot in snapshots] == ["exact"]
    candidate_query = statements[0].compile()
    assert '"cohort/_id"' in candidate_query.params.values()
    assert f'"{cohort_id.replace("_", "/_")}"' in candidate_query.params.values()
    assert statements[1].compile().params == {"run_id_1": ["exact"]}
    assert statements[2].compile().params == {"run_id_1": ["exact"]}


def test_prospective_cohort_query_sqlite_escapes_id_and_filters_false_positives(
    monkeypatch,
):
    cohort_id = "tw_2330_o2o_v1"
    exact_payload = research_run_repository.json_dumps(
        {"prospective_evidence": {"cohort_id": cohort_id}}
    )
    false_positive_payload = research_run_repository.json_dumps(
        {
            "cohort_id": cohort_id,
            "prospective_evidence": {"cohort_id": "tw_all_active_o2o_v1"},
        }
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ResearchRun.__table__,
            ResearchRunLiquidityCoverage.__table__,
        ],
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    with testing_session_local() as session:
        session.add_all(
            [
                ResearchRun(
                    run_id="exact-sqlite",
                    status="succeeded",
                    symbols_json="[]",
                    created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    request_payload_json=exact_payload,
                ),
                ResearchRun(
                    run_id="false-positive-sqlite",
                    status="succeeded",
                    symbols_json="[]",
                    created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                    request_payload_json=false_positive_payload,
                ),
                ResearchRunLiquidityCoverage(
                    run_id="exact-sqlite",
                    bucket_key="large",
                    bucket_label="Large",
                    full_universe_count=4,
                    execution_universe_count=3,
                    full_universe_ratio=0.4,
                    execution_coverage_ratio=0.75,
                ),
                ResearchRunLiquidityCoverage(
                    run_id="exact-sqlite",
                    bucket_key="active",
                    bucket_label="Active",
                    full_universe_count=6,
                    execution_universe_count=6,
                    full_universe_ratio=0.6,
                    execution_coverage_ratio=1.0,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)
    snapshots = research_run_repository.list_prospective_cohort_run_snapshots(
        cohort_id
    )

    assert [snapshot["run_id"] for snapshot in snapshots] == ["exact-sqlite"]
    assert snapshots[0]["request_payload"]["prospective_evidence"]["cohort_id"] == (
        cohort_id
    )
    assert [
        item["bucket_key"]
        for item in snapshots[0]["liquidity_bucket_coverages"]
    ] == ["active", "large"]


def test_prospective_cohort_query_batches_rows_and_preserves_global_order(
    monkeypatch,
):
    cohort_id = "tw_2330_o2o_v1"
    candidate_rows = []
    rows_by_id = {}
    base_created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(1001):
        run_id = f"run-{index:04d}"
        request_payload = research_run_repository.json_dumps(
            {"prospective_evidence": {"cohort_id": cohort_id}}
        )
        created_at = base_created_at + timedelta(seconds=index)
        candidate_rows.append((run_id, request_payload))
        rows_by_id[run_id] = ResearchRun(
            run_id=run_id,
            status="succeeded",
            created_at=created_at,
            request_payload_json=request_payload,
        )

    statements = []
    partition_sizes = []
    row_batch_sizes = []
    coverage_batch_sizes = []
    candidate_result_exhausted = []

    class _CandidateResult:
        def yield_per(self, size):
            assert size == 500
            return self

        def partitions(self, size):
            partition_sizes.append(size)
            for start in range(0, len(candidate_rows), size):
                yield candidate_rows[start : start + size]
            candidate_result_exhausted.append(True)

    class _RowResult:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            statements.append(statement)
            if len(statements) == 1:
                return _CandidateResult()
            assert candidate_result_exhausted == [True]
            batch_index = (len(statements) - 2) // 2
            start = batch_index * 500
            batch_ids = [
                run_id
                for run_id, _ in candidate_rows[start : start + 500]
            ]
            if len(statements) % 2 == 1:
                coverage_batch_sizes.append(len(batch_ids))
                return _RowResult([])
            row_batch_sizes.append(len(batch_ids))
            return _RowResult(
                [rows_by_id[run_id] for run_id in reversed(batch_ids)]
            )

    monkeypatch.setattr(research_run_repository, "SessionLocal", _Session)

    snapshots = research_run_repository.list_prospective_cohort_run_snapshots(
        cohort_id
    )

    assert partition_sizes == [500]
    assert row_batch_sizes == [500, 500, 1]
    assert coverage_batch_sizes == [500, 500, 1]
    assert len(statements) == 7
    assert [snapshot["run_id"] for snapshot in snapshots] == [
        f"run-{index:04d}" for index in range(1001)
    ]


def test_project_persisted_snapshot_requires_private_metadata_keys():
    with pytest.raises(ValueError, match=r"_artifact_presence.*_version_pack_values"):
        research_run_projection.project_persisted_snapshot(
            {"run_id": "missing-metadata"},
            include_artifacts=True,
        )


def test_project_persisted_snapshot_parses_model_diagnostics_once(monkeypatch):
    row = ResearchRun(
        run_id="diagnostics-once",
        status="succeeded",
        request_payload_json=None,
        metrics_json="{}",
        model_diagnostics_json='{"task": "regression", "sample_count": 0}',
        equity_curve_json="[]",
        signals_json="[]",
        validation_outcome_json='{"method": "walk_forward", "metrics": {}}',
        baselines_json="{}",
        comparison_eligibility="research_only_comparable",
    )
    snapshot = research_run_repository._run_row_to_snapshot(row)
    original_parser = research_run_projection._model_diagnostics_from_payload
    parser_calls = 0

    def _counting_parser(value):
        nonlocal parser_calls
        parser_calls += 1
        return original_parser(value)

    monkeypatch.setattr(
        research_run_projection,
        "_model_diagnostics_from_payload",
        _counting_parser,
    )

    projected = research_run_projection.project_persisted_snapshot(
        snapshot,
        include_artifacts=False,
    )

    assert parser_calls == 1
    assert projected["model_diagnostics"]["sample_count"] == 0
    assert projected["model_diagnostics"]["actual_vs_predicted"] == []


@pytest.mark.parametrize(
    "legacy_state",
    ["native_missing_supported", "core_data_gaps_filtered"],
)
def test_run_projection_preserves_legacy_missing_feature_metadata(legacy_state):
    row = ResearchRun(
        run_id="legacy-missing-feature-policy",
        status="succeeded",
        missing_feature_policy_state=legacy_state,
        missing_feature_policy_version="xgboost_native_missing_v1",
    )

    snapshot = research_run_repository._run_row_to_snapshot(row)
    projected = research_run_projection.project_persisted_snapshot(
        snapshot,
        include_artifacts=False,
    )

    assert snapshot["missing_feature_policy_state"] == legacy_state
    assert snapshot["_version_pack_values"]["missing_feature_policy_version"] == (
        "xgboost_native_missing_v1"
    )
    assert projected["missing_feature_policy_state"] == legacy_state
    assert projected["missing_feature_policy_version"] == "xgboost_native_missing_v1"


def test_run_row_to_snapshot_parses_reused_json_fields_once(monkeypatch):
    equity_curve_json = '[{"equity": 1.0}]'
    signals_json = '[{"symbol": "2330"}]'
    scoring_factor_ids_json = '["momentum"]'
    row = ResearchRun(
        run_id="reused-json-fields",
        status="succeeded",
        equity_curve_json=equity_curve_json,
        signals_json=signals_json,
        scoring_factor_ids_json=scoring_factor_ids_json,
    )
    original_json_loads = research_run_repository.json_loads
    calls = {
        equity_curve_json: 0,
        signals_json: 0,
        scoring_factor_ids_json: 0,
    }

    def _counting_json_loads(value, default):
        if value in calls:
            calls[value] += 1
        return original_json_loads(value, default)

    monkeypatch.setattr(
        research_run_repository,
        "json_loads",
        _counting_json_loads,
    )

    snapshot = research_run_repository._run_row_to_snapshot(row)

    assert calls == {
        equity_curve_json: 1,
        signals_json: 1,
        scoring_factor_ids_json: 1,
    }
    assert snapshot["equity_curve"] == [{"equity": 1.0}]
    assert snapshot["signals"] == [{"symbol": "2330"}]
    assert snapshot["scoring_factor_ids"] == ["momentum"]
    assert snapshot["_version_pack_values"]["scoring_factor_ids"] == ["momentum"]
    assert snapshot["_artifact_presence"]["equity_curve"] is True
    assert snapshot["_artifact_presence"]["signals"] is True


@pytest.mark.parametrize(
    ("stored_value", "expected_value"),
    [
        (None, []),
        ("{not-json", []),
        ("null", None),
    ],
)
def test_run_row_to_snapshot_preserves_json_fallback_behavior(
    stored_value,
    expected_value,
):
    row = ResearchRun(
        run_id="json-fallback-behavior",
        status="succeeded",
        equity_curve_json=stored_value,
        signals_json=stored_value,
        scoring_factor_ids_json=stored_value,
    )

    snapshot = research_run_repository._run_row_to_snapshot(row)

    assert snapshot["equity_curve"] == expected_value
    assert snapshot["signals"] == expected_value
    assert snapshot["scoring_factor_ids"] == expected_value
    assert snapshot["_version_pack_values"]["scoring_factor_ids"] == expected_value
    assert snapshot["_artifact_presence"]["equity_curve"] is False
    assert snapshot["_artifact_presence"]["signals"] is False


def test_legacy_run_without_registry_version_projects_unavailable() -> None:
    row = ResearchRun(
        run_id="legacy-feature-registry",
        status="succeeded",
        request_payload_json='{"runtime_mode":"runtime_compatibility_mode"}',
    )

    snapshot = research_run_repository._run_row_to_snapshot(row)

    assert snapshot["feature_registry_version"] is None


def test_legacy_top_level_registry_version_migrates_into_metadata() -> None:
    row = ResearchRun(
        run_id="legacy-top-level-registry",
        status="succeeded",
        request_payload_json=(
            '{"market":"TW",'
            '"feature_registry_version":"technical_feature_registry_v2"}'
        ),
    )

    snapshot = research_run_repository._run_row_to_snapshot(row)

    assert snapshot["feature_registry_version"] == "technical_feature_registry_v2"
    assert "feature_registry_version" not in snapshot["request_payload"]
    assert snapshot["request_payload"]["market"] == "TW"


def test_none_request_payload_round_trips_with_registry_metadata(monkeypatch):
    feature_registry_version = "technical_feature_registry_v3"
    persisted_payload = research_run_repository._build_persisted_request_payload(
        None,
        feature_registry_version=feature_registry_version,
    )

    request_payload, result_metadata = (
        research_run_repository._split_persisted_request_payload(persisted_payload)
    )

    assert request_payload is None
    assert result_metadata == {
        "feature_registry_version": feature_registry_version,
    }
    assert persisted_payload["_result_metadata"] == {
        "feature_registry_version": feature_registry_version,
        "request_payload_absent": True,
    }

    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine, tables=[ResearchRun.__table__])
    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        session.add(
            ResearchRun(
                run_id="none-request-payload",
                status="succeeded",
                symbols_json="[]",
                request_payload_json=research_run_repository.json_dumps(
                    persisted_payload
                ),
            )
        )
        session.commit()

    snapshot = research_run_repository._run_row_to_snapshot(
        ResearchRun(
            run_id="none-request-payload-snapshot",
            status="succeeded",
            request_payload_json=research_run_repository.json_dumps(
                persisted_payload
            ),
        )
    )

    assert snapshot["request_payload"] is None
    assert snapshot["feature_registry_version"] == feature_registry_version
    assert (
        research_run_repository.get_research_run_request_payload(
            "none-request-payload"
        )
        is None
    )


def test_empty_request_payload_remains_empty_with_registry_metadata() -> None:
    persisted_payload = research_run_repository._build_persisted_request_payload(
        {},
        feature_registry_version="technical_feature_registry_v3",
    )

    request_payload, result_metadata = (
        research_run_repository._split_persisted_request_payload(persisted_payload)
    )

    assert request_payload == {}
    assert result_metadata == {
        "feature_registry_version": "technical_feature_registry_v3",
    }


def test_project_persisted_snapshot_does_not_mutate_reused_snapshot():
    row = ResearchRun(
        run_id="reused-snapshot",
        status="succeeded",
        request_payload_json=None,
        metrics_json="{}",
        model_diagnostics_json=(
            '{"task": "regression", "sample_count": 1, '
            '"actual_vs_predicted": [{"actual": 0.1, "predicted": 0.2}]}'
        ),
        equity_curve_json="[]",
        signals_json="[]",
        validation_outcome_json='{"method": "walk_forward", "metrics": {}}',
        baselines_json="{}",
        comparison_eligibility="research_only_comparable",
    )
    snapshot = research_run_repository._run_row_to_snapshot(row)
    original_artifact_presence = dict(snapshot["_artifact_presence"])

    summary = research_run_projection.project_persisted_snapshot(
        snapshot,
        include_artifacts=False,
    )
    detail = research_run_projection.project_persisted_snapshot(
        snapshot,
        include_artifacts=True,
    )

    assert snapshot["_artifact_presence"] == original_artifact_presence
    assert summary["model_diagnostics"]["actual_vs_predicted"] == []
    assert detail["model_diagnostics"]["actual_vs_predicted"] == [
        {"actual": 0.1, "predicted": 0.2}
    ]


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
        "feature_registry_version": "technical_feature_registry_v3",
        "market": None,
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
            "market": "TW",
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
        "missing_feature_policy_state": "complete_case_applied",
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
                "missing_feature_policy_version": "complete_case_model_inputs_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)
    loaded = research_run_projection.get_research_run_record("run_123")

    assert loaded["run_id"] == "run_123"
    assert loaded["feature_registry_version"] == "technical_feature_registry_v3"
    assert "feature_registry_version" not in loaded["request_payload"]
    with testing_session_local() as session:
        stored_request = research_run_repository.json_loads(
            session.get(ResearchRun, "run_123").request_payload_json,
            None,
        )
    assert stored_request["_result_metadata"] == {
        "feature_registry_version": "technical_feature_registry_v3"
    }
    assert loaded["market"] is None
    assert loaded["request_payload"]["market"] == "TW"
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
    assert loaded["warnings"] == []
    assert loaded["comparison_caveats"] == [
        {
            "code": TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE,
            "label": TW_POINT_IN_TIME_MEMBERSHIP_WARNING,
            "severity": "note",
        }
    ]
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
    assert checks["backtest_report_discipline"]["status"] == "warning"
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
    assert checks["text_evidence_summary"]["status"] == "warning"
    assert checks["text_evidence_summary"]["result"]["caveat_count"] == 1
    assert checks["text_evidence_summary"]["result"]["source_text_count"] == 1
    assert checks["text_evidence_summary"]["result"]["summary_text"] == (
        TW_POINT_IN_TIME_MEMBERSHIP_WARNING
    )
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
        "REVIEW_ARTIFACTS_MISSING",
        TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE,
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


def test_list_research_run_snapshots_batches_liquidity_coverages(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[ResearchRun.__table__, ResearchRunLiquidityCoverage.__table__],
    )
    with testing_session_local() as session:
        session.add_all(
            [
                ResearchRun(
                    run_id="run-old",
                    status="succeeded",
                    symbols_json="[]",
                    created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ),
                ResearchRun(
                    run_id="run-new",
                    status="succeeded",
                    symbols_json="[]",
                    created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                ),
                ResearchRunLiquidityCoverage(
                    run_id="run-new",
                    bucket_key="large",
                    bucket_label="Large",
                    full_universe_count=4,
                    execution_universe_count=3,
                    full_universe_ratio=0.4,
                    execution_coverage_ratio=0.75,
                ),
                ResearchRunLiquidityCoverage(
                    run_id="run-new",
                    bucket_key="active",
                    bucket_label="Active",
                    full_universe_count=6,
                    execution_universe_count=6,
                    full_universe_ratio=0.6,
                    execution_coverage_ratio=1.0,
                ),
            ]
        )
        session.commit()

    select_statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture_selects(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    monkeypatch.setattr(research_run_repository, "SessionLocal", testing_session_local)

    snapshots = research_run_repository.list_research_run_snapshots()

    assert len(select_statements) == 2
    assert [snapshot["run_id"] for snapshot in snapshots] == ["run-new", "run-old"]
    assert [
        coverage["bucket_key"]
        for coverage in snapshots[0]["liquidity_bucket_coverages"]
    ] == ["active", "large"]
    assert snapshots[1]["liquidity_bucket_coverages"] == []


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
        "missing_feature_policy_state": "complete_case_applied",
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
                "missing_feature_policy_version": "complete_case_model_inputs_v1",
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
        "missing_feature_policy_state": "complete_case_applied",
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
                "missing_feature_policy_version": "complete_case_model_inputs_v1",
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
        "missing_feature_policy_state": "complete_case_applied",
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
                "missing_feature_policy_version": "complete_case_model_inputs_v1",
                "execution_cost_model_version": "fees_slippage_only_v1",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)

    with testing_session_local() as session:
        observation = session.query(MicrostructureObservation).one()

    assert observation.trading_date.isoformat() == "2024-01-02"
