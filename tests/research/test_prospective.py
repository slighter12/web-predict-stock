from datetime import date, datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

import backend.research.services.execution as execution_service
import backend.research.services.prospective as prospective_service
import backend.research.services.registry as registry_service
from backend.research.api import PublicResearchRunCreateRequest
from backend.research.contracts.runs import ResearchRunCreateRequest


def _request(*, prospective: bool = False, **overrides) -> ResearchRunCreateRequest:
    payload = {
        "runtime_mode": "runtime_compatibility_mode",
        "market": "TW",
        "symbols": ["2330"],
        "date_range": {"start": "2024-01-01", "end": "2024-01-04"},
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": [{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        "model": {"type": "extra_trees", "params": {}},
        "direction_model": {"type": "extra_trees", "params": {}},
        "strategy": {
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 1,
            "allow_proactive_sells": True,
        },
        "execution": {"slippage": 0.001, "fees": 0.002},
        "execution_route": "research_only",
    }
    if prospective:
        payload["prospective_evidence"] = {
            "mode": "strict_v1",
            "cohort_id": "tw_2330_o2o_v1",
            "basis_date": "2024-01-04",
            "full_universe_symbols": ["2330"],
        }
    payload.update(overrides)
    return ResearchRunCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"market": "US"}, "requires market='TW'"),
        ({"return_target": "close_to_close"}, "requires open_to_open"),
        ({"horizon_days": 2}, "requires open_to_open"),
        (
            {"execution_route": "simulation_internal_v1"},
            "requires execution_route='research_only'",
        ),
        (
            {
                "features": [
                    {"name": "ma", "window": 5, "source": "close", "shift": 2}
                ]
            },
            "requires every feature shift=1",
        ),
    ],
)
def test_strict_prospective_contract_rejects_non_frozen_configuration(
    override, message
):
    with pytest.raises(ValidationError, match=message):
        _request(prospective=True, **override)


def test_strict_prospective_contract_rejects_duplicate_universe_snapshot():
    with pytest.raises(ValidationError, match="full_universe_symbols must not contain duplicates"):
        _request(
            prospective=True,
            prospective_evidence={
                "mode": "strict_v1",
                "cohort_id": "tw_all_active_o2o_v1",
                "basis_date": "2024-01-04",
                "full_universe_symbols": ["2330", "2330"],
            },
        )


def test_strict_prospective_contract_rejects_execution_symbol_outside_snapshot():
    with pytest.raises(ValidationError, match="symbols must be a subset"):
        _request(
            prospective=True,
            prospective_evidence={
                "mode": "strict_v1",
                "cohort_id": "tw_all_active_o2o_v1",
                "basis_date": "2024-01-04",
                "full_universe_symbols": ["2317"],
            },
        )


def test_public_strict_prospective_contract_rejects_non_o2o_target():
    internal_payload = _request(prospective=True).model_dump(mode="json")
    payload = {
        name: value
        for name, value in internal_payload.items()
        if name in PublicResearchRunCreateRequest.model_fields
    }
    payload["return_target"] = "close_to_close"

    with pytest.raises(ValidationError, match="requires open_to_open"):
        PublicResearchRunCreateRequest.model_validate(payload)


def test_non_strict_request_remains_compatible_with_non_strict_feature_shift():
    request = _request(
        return_target="close_to_close",
        horizon_days=2,
        execution_route="simulation_internal_v1",
        features=[{"name": "ma", "window": 5, "source": "close", "shift": 2}],
    )

    assert request.prospective_evidence is None
    assert request.features[0].shift == 2


def test_success_request_payload_writes_timezone_aware_frozen_timestamp_for_first_strict_run(
    monkeypatch,
):
    frozen_at = datetime(2024, 1, 4, 5, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(
        registry_service, "get_research_run_record", lambda run_id: {"request_payload": {}}
    )
    monkeypatch.setattr(registry_service, "utc_now", lambda: frozen_at)

    payload = registry_service._success_request_payload(
        run_id="strict-first", request=_request(prospective=True)
    )

    assert payload["prospective_evidence"]["signal_frozen_at"] == frozen_at.isoformat()


def test_success_request_payload_preserves_existing_strict_frozen_timestamp_on_retry(
    monkeypatch,
):
    existing_timestamp = "2024-01-04T05:25:00+00:00"
    monkeypatch.setattr(
        registry_service,
        "get_research_run_record",
        lambda run_id: {
            "request_payload": {
                "prospective_evidence": {"signal_frozen_at": existing_timestamp}
            }
        },
    )
    monkeypatch.setattr(
        registry_service,
        "utc_now",
        lambda: pytest.fail("a retry must preserve its original frozen timestamp"),
    )

    payload = registry_service._success_request_payload(
        run_id="strict-retry", request=_request(prospective=True)
    )

    assert payload["prospective_evidence"]["signal_frozen_at"] == existing_timestamp


def test_success_request_payload_leaves_non_strict_request_unchanged(monkeypatch):
    monkeypatch.setattr(
        registry_service,
        "get_research_run_record",
        lambda run_id: pytest.fail("non-strict payload must not read persisted state"),
    )

    payload = registry_service._success_request_payload(
        run_id="ordinary", request=_request()
    )

    assert payload["prospective_evidence"] is None


class _Regressor:
    def __init__(self, captured):
        self._captured = captured

    def predict(self, frame):
        self._captured.append(frame.copy())
        return [float(frame.iloc[0, 0])]


class _Classifier:
    classes_ = [0, 1]

    def predict_proba(self, frame):
        return [[0.2, 0.8]]


def _symbol_data() -> list[dict]:
    index = pd.to_datetime(["2024-01-03", "2024-01-04"])
    return [
        {
            "symbol": "2330",
            "X": pd.DataFrame({"MA_5": [10.0]}, index=index[:1]),
            "y": pd.Series([0.01], index=index[:1]),
            "prediction_features": pd.DataFrame({"MA_5": [20.0, 30.0]}, index=index),
            "prospective_prediction_features": pd.DataFrame(
                {"MA_5": [200.0, 300.0]}, index=index
            ),
        }
    ]


def test_strict_forward_signal_uses_unshifted_basis_features_and_normal_mode_is_unchanged(
    monkeypatch,
):
    captured: list[pd.DataFrame] = []
    monkeypatch.setattr(
        execution_service.model_service,
        "fit_regressor",
        lambda **kwargs: _Regressor(captured),
    )
    monkeypatch.setattr(
        execution_service.model_service,
        "fit_calibrated_direction_classifier",
        lambda **kwargs: (_Classifier(), None, 1),
    )

    strict_request = _request(prospective=True)
    strict_signals, strict_warning = execution_service.build_forward_opinion_signals(
        _symbol_data(), strict_request, strict_request.strategy
    )

    assert strict_warning is None
    assert strict_signals[0]["date"] == date(2024, 1, 4)
    assert strict_signals[0]["score"] == 300.0
    assert captured[-1].iloc[0, 0] == 300.0

    normal_request = _request()
    normal_signals, normal_warning = execution_service.build_forward_opinion_signals(
        _symbol_data(), normal_request, normal_request.strategy
    )

    assert normal_warning is None
    assert normal_signals[0]["score"] == 30.0
    assert captured[-1].iloc[0, 0] == 30.0


def test_strict_forward_signal_rejects_feature_date_other_than_frozen_basis_date(monkeypatch):
    monkeypatch.setattr(
        execution_service.model_service,
        "fit_regressor",
        lambda **kwargs: pytest.fail("model must not be fitted for a mismatched basis date"),
    )
    request = _request(prospective=True)
    symbol_data = _symbol_data()
    symbol_data[0]["prospective_prediction_features"] = symbol_data[0][
        "prospective_prediction_features"
    ].iloc[:1]

    signals, warning = execution_service.build_forward_opinion_signals(
        symbol_data, request, request.strategy
    )

    assert signals == []
    assert warning == (
        "Prospective opinion unavailable: strict evidence basis_date does not "
        "match the latest unshifted feature date."
    )


def _strict_record(
    run_id: str,
    *,
    created_at: str = "2024-01-04T13:30:00+08:00",
    signal_frozen_at: str = "2024-01-04T13:25:00+08:00",
) -> dict:
    evidence = prospective_service.prospective_evidence_payload(
        cohort_id=prospective_service.COHORT_2330,
        basis_date=date(2024, 1, 4),
        full_universe_symbols=["2330"],
    )
    evidence["signal_frozen_at"] = signal_frozen_at
    return {
        "run_id": run_id,
        "status": "succeeded",
        "created_at": created_at,
        "request_payload": {
            "runtime_mode": "vnext_spec_mode",
            "default_bundle_version": "research_spec_v1",
            "market": "TW",
            "symbols": ["2330"],
            "return_target": "open_to_open",
            "horizon_days": 1,
            "execution_route": "research_only",
            "features": [
                {"name": "ma", "window": 5, "source": "close", "shift": 1},
                {"name": "rsi", "window": 14, "source": "close", "shift": 1},
            ],
            "model": {
                "type": "extra_trees",
                "params": {"n_estimators": 200, "random_state": 42, "n_jobs": -1},
            },
            "direction_model": {
                "type": "extra_trees",
                "params": {"n_estimators": 200, "random_state": 42, "n_jobs": -1},
            },
            "validation": {"method": "walk_forward", "splits": 3, "test_size": 0.2},
            "baselines": ["buy_and_hold"],
            "strategy": {
                "type": "research_v1",
                "threshold": None,
                "top_n": None,
                "allow_proactive_sells": True,
            },
            "execution": {"fees": 0.002, "slippage": 0.001},
            "prospective_evidence": evidence,
        },
        "signals": [
            {
                "date": "2024-01-04",
                "symbol": "2330",
                "score": 0.05,
                "position": 1.0,
                "up_probability": 0.8,
                "signal_kind": "forward_opinion",
            }
        ],
    }


def _bars(*rows: tuple[str, float]) -> dict[str, list[prospective_service.EligibleBar]]:
    return {
        "2330": [
            prospective_service.EligibleBar(
                date=date.fromisoformat(day),
                open=open_price,
                high=open_price,
                low=open_price,
                close=open_price,
                source="twse",
                raw_payload_id=1,
            )
            for day, open_price in rows
        ]
    }


def test_cohort_evaluator_keeps_unresolved_outcome_out_of_completed_sample(monkeypatch):
    monkeypatch.setattr(
        prospective_service,
        "list_cohort_run_records",
        lambda cohort_id: [_strict_record("not-ready")],
    )
    monkeypatch.setattr(
        prospective_service,
        "load_eligible_bars",
        lambda *args, **kwargs: _bars(("2024-01-05", 100.0)),
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert result["runs"][0]["status"] == "not_ready"
    assert result["runs"][0]["outcomes"] == [{"symbol": "2330", "status": "not_ready"}]
    assert result["completed_trading_days"] == 0
    assert result["resolved_signal_count"] == 0
    assert result["metrics"]["rmse"] is None


def test_cohort_evaluator_calculates_observed_o2o_return_direction_and_brier(monkeypatch):
    monkeypatch.setattr(
        prospective_service,
        "list_cohort_run_records",
        lambda cohort_id: [_strict_record("resolved")],
    )
    monkeypatch.setattr(
        prospective_service,
        "load_eligible_bars",
        lambda *args, **kwargs: _bars(
            ("2024-01-04", 99.0), ("2024-01-05", 100.0), ("2024-01-08", 110.0)
        ),
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    outcome = result["runs"][0]["outcomes"][0]
    assert result["runs"][0]["status"] == "resolved"
    assert outcome["actual_return"] == pytest.approx(0.1)
    assert outcome["actual_direction"] == 1
    assert outcome["direction_hit"] == 1
    assert outcome["brier"] == pytest.approx(0.04)
    assert result["completed_trading_days"] == 1
    assert result["metrics"]["rmse"] == pytest.approx(0.05)
    assert result["metrics"]["mae"] == pytest.approx(0.05)
    assert result["metrics"]["direction_accuracy"] == 1.0
    assert result["metrics"]["brier"] == pytest.approx(0.04)
    assert result["metrics"]["gross_position_return"] == pytest.approx(0.1)
    assert result["metrics"]["net_position_return"] < 0.1


def test_cohort_evaluator_uses_frozen_timestamp_not_record_created_at(monkeypatch):
    monkeypatch.setattr(
        prospective_service,
        "list_cohort_run_records",
        lambda cohort_id: [_strict_record("late", created_at="2024-01-05T00:01:00+08:00")],
    )
    monkeypatch.setattr(
        prospective_service,
        "load_eligible_bars",
        lambda *args, **kwargs: _bars(
            ("2024-01-04", 99.0), ("2024-01-05", 100.0), ("2024-01-08", 110.0)
        ),
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert result["runs"][0]["status"] == "resolved"


@pytest.mark.parametrize(
    ("signal_frozen_at", "expected_issue"),
    [
        (None, "invalid_signal_frozen_at"),
        ("2024-01-05T00:01:00+08:00", "signal_frozen_at_not_on_basis_date"),
    ],
)
def test_cohort_evaluator_requires_valid_same_day_frozen_timestamp(
    monkeypatch, signal_frozen_at, expected_issue
):
    record = _strict_record("invalid-freeze")
    if signal_frozen_at is None:
        record["request_payload"]["prospective_evidence"].pop("signal_frozen_at")
    else:
        record["request_payload"]["prospective_evidence"]["signal_frozen_at"] = (
            signal_frozen_at
        )
    monkeypatch.setattr(
        prospective_service, "list_cohort_run_records", lambda cohort_id: [record]
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert result["runs"][0]["status"] == "invalid"
    assert result["runs"][0]["issues"] == [expected_issue]


def test_cohort_evaluator_rejects_duplicate_basis_date_without_double_counting(monkeypatch):
    monkeypatch.setattr(
        prospective_service,
        "list_cohort_run_records",
        lambda cohort_id: [_strict_record("first"), _strict_record("duplicate")],
    )
    monkeypatch.setattr(
        prospective_service,
        "load_eligible_bars",
        lambda *args, **kwargs: _bars(
            ("2024-01-04", 99.0), ("2024-01-05", 100.0), ("2024-01-08", 110.0)
        ),
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert [run["status"] for run in result["runs"]] == ["invalid", "invalid"]
    assert [run["issues"] for run in result["runs"]] == [
        ["duplicate_basis_date"],
        ["duplicate_basis_date"],
    ]
    assert result["completed_trading_days"] == 0
    assert result["resolved_signal_count"] == 0


def test_cohort_evaluator_rejects_signal_date_that_differs_from_basis_date(monkeypatch):
    record = _strict_record("wrong-signal-date")
    record["signals"][0]["date"] = "2024-01-03"
    monkeypatch.setattr(
        prospective_service, "list_cohort_run_records", lambda cohort_id: [record]
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert result["runs"][0]["status"] == "invalid"
    assert result["runs"][0]["issues"] == ["incomplete_forward_signals"]


def test_cohort_evaluator_rejects_changed_frozen_recipe(monkeypatch):
    record = _strict_record("changed-recipe")
    record["request_payload"]["model"]["params"]["n_estimators"] = 100
    monkeypatch.setattr(
        prospective_service, "list_cohort_run_records", lambda cohort_id: [record]
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_2330)

    assert result["runs"][0]["status"] == "invalid"
    assert result["runs"][0]["issues"] == ["strict_model_recipe_mismatch"]


def test_all_active_evaluator_rejects_execution_coverage_below_95_percent(monkeypatch):
    record = _strict_record("insufficient-coverage")
    snapshot = [f"{number:04d}" for number in range(20)]
    evidence = prospective_service.prospective_evidence_payload(
        cohort_id=prospective_service.COHORT_ALL_ACTIVE,
        basis_date=date(2024, 1, 4),
        full_universe_symbols=snapshot,
    )
    evidence["signal_frozen_at"] = "2024-01-04T13:25:00+08:00"
    record["request_payload"]["prospective_evidence"] = evidence
    monkeypatch.setattr(
        prospective_service, "list_cohort_run_records", lambda cohort_id: [record]
    )

    result = prospective_service.evaluate_cohort(prospective_service.COHORT_ALL_ACTIVE)

    assert result["runs"][0]["status"] == "invalid"
    assert result["runs"][0]["issues"] == ["strict_execution_coverage_mismatch"]


def test_2330_preflight_requires_2330_to_be_data_ready(monkeypatch):
    monkeypatch.setattr(
        prospective_service,
        "load_official_no_data_dates",
        lambda **kwargs: set(),
    )
    monkeypatch.setattr(
        prospective_service,
        "_model_ready_symbol",
        lambda **kwargs: "forward_signal_unavailable",
    )

    result = prospective_service.preflight_cohort(
        cohort_id=prospective_service.COHORT_2330,
        basis_date=date(2024, 1, 4),
    )

    assert result["full_universe_symbols"] == ["2330"]
    assert result["execution_symbols"] == []
    assert result["status"] == "no-opinion"


@pytest.mark.parametrize(
    ("ready_count", "expected_status"), [(94, "no-opinion"), (95, "ready")],
)
def test_all_active_preflight_applies_95_percent_coverage_gate(
    monkeypatch, ready_count, expected_status
):
    symbols = [f"{number:04d}" for number in range(100)]
    monkeypatch.setattr(prospective_service, "active_tw_profile_symbols", lambda: symbols)
    monkeypatch.setattr(
        prospective_service,
        "load_official_no_data_dates",
        lambda **kwargs: set(),
    )
    monkeypatch.setattr(
        prospective_service,
        "_model_ready_symbol",
        lambda *, symbol, **kwargs: None if int(symbol) < ready_count else "model_not_ready",
    )

    result = prospective_service.preflight_cohort(
        cohort_id=prospective_service.COHORT_ALL_ACTIVE,
        basis_date=date(2024, 1, 4),
    )

    assert result["execution_coverage_ratio"] == pytest.approx(ready_count / 100)
    assert result["status"] == expected_status
