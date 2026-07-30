from __future__ import annotations

import json
import sys
from datetime import date
from types import SimpleNamespace

from backend.platform.errors import DataAccessError, ExternalFetchError


def test_runner_reuses_one_existing_valid_run(capsys, monkeypatch, load_script):
    module = load_script(
        "run_tw_prospective_cohorts.py",
        "run_tw_prospective_cohorts_existing",
    )
    monkeypatch.setattr(
        module,
        "valid_successful_cohort_runs",
        lambda **kwargs: [{"run_id": "existing-run"}],
    )
    monkeypatch.setattr(
        module,
        "preflight_cohort",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("existing runs must skip preflight")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tw_prospective_cohorts.py",
            "--basis-date",
            "2024-01-04",
            "--cohort",
            "2330",
        ],
    )

    assert module.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["cohorts"] == [
        {
            "cohort_id": module.COHORT_2330,
            "basis_date": "2024-01-04",
            "status": "existing",
            "run_id": "existing-run",
        }
    ]


def test_runner_fails_closed_for_multiple_existing_valid_runs(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "run_tw_prospective_cohorts.py",
        "run_tw_prospective_cohorts_duplicate",
    )
    monkeypatch.setattr(
        module,
        "valid_successful_cohort_runs",
        lambda **kwargs: [{"run_id": "first"}, {"run_id": "second"}],
    )
    monkeypatch.setattr(
        module,
        "preflight_cohort",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("duplicate runs must skip preflight")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tw_prospective_cohorts.py",
            "--basis-date",
            "2024-01-04",
            "--cohort",
            "2330",
        ],
    )

    assert module.main() == 1

    report = json.loads(capsys.readouterr().out)["cohorts"][0]
    assert report["status"] == "error"
    assert report["failure_kind"] == "duplicate_valid_runs"
    assert report["run_ids"] == ["first", "second"]


def test_runner_creates_with_deterministic_run_id(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "run_tw_prospective_cohorts.py",
        "run_tw_prospective_cohorts_create",
    )
    basis_date = date(2024, 1, 4)
    preflight = {
        "cohort_id": module.COHORT_2330,
        "basis_date": basis_date.isoformat(),
        "full_universe_symbols": ["2330"],
        "execution_symbols": ["2330"],
        "status": "ready",
    }
    calls = []
    monkeypatch.setattr(module, "valid_successful_cohort_runs", lambda **kwargs: [])
    monkeypatch.setattr(module, "preflight_cohort", lambda **kwargs: preflight)
    monkeypatch.setattr(
        module,
        "create_research_run",
        lambda request, **kwargs: calls.append(kwargs)
        or SimpleNamespace(run_id=kwargs["run_id"]),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tw_prospective_cohorts.py",
            "--basis-date",
            basis_date.isoformat(),
            "--cohort",
            "2330",
        ],
    )

    assert module.main() == 0

    expected_run_id = module.prospective_run_id(
        cohort_id=module.COHORT_2330,
        basis_date=basis_date,
    )
    assert calls[0]["run_id"] == expected_run_id
    assert json.loads(capsys.readouterr().out)["cohorts"][0]["run_id"] == (
        expected_run_id
    )


def test_runner_isolates_expected_failure_and_continues_both_cohorts(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "run_tw_prospective_cohorts.py",
        "run_tw_prospective_cohorts_isolated_failure",
    )
    basis_date = date(2024, 1, 4)

    def preflight(*, cohort_id, basis_date):
        symbol = "2330" if cohort_id == module.COHORT_2330 else "2317"
        return {
            "cohort_id": cohort_id,
            "basis_date": basis_date.isoformat(),
            "full_universe_symbols": [symbol],
            "execution_symbols": [symbol],
            "status": "ready",
        }

    created = []

    def create_run(request, **kwargs):
        cohort_id = request.prospective_evidence.cohort_id
        if cohort_id == module.COHORT_2330:
            raise ExternalFetchError("2330 cohort failed")
        created.append(cohort_id)
        return SimpleNamespace(run_id=kwargs["run_id"])

    monkeypatch.setattr(module, "valid_successful_cohort_runs", lambda **kwargs: [])
    monkeypatch.setattr(module, "preflight_cohort", preflight)
    monkeypatch.setattr(module, "create_research_run", create_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tw_prospective_cohorts.py",
            "--basis-date",
            basis_date.isoformat(),
        ],
    )

    assert module.main() == 1

    reports = json.loads(capsys.readouterr().out)["cohorts"]
    assert reports[0]["status"] == "error"
    assert reports[0]["failure_kind"] == "ExternalFetchError"
    assert reports[0]["reason"] == "2330 cohort failed"
    assert reports[1]["status"] == "created"
    assert created == [module.COHORT_ALL_ACTIVE]


def test_runner_isolates_lookup_failure_and_continues_both_cohorts(
    caplog, capsys, monkeypatch, load_script
):
    module = load_script(
        "run_tw_prospective_cohorts.py",
        "run_tw_prospective_cohorts_lookup_failure",
    )
    basis_date = date(2024, 1, 4)

    def existing_runs(*, cohort_id, basis_date):
        if cohort_id == module.COHORT_2330:
            raise DataAccessError("research registry unavailable")
        return []

    def preflight(*, cohort_id, basis_date):
        return {
            "cohort_id": cohort_id,
            "basis_date": basis_date.isoformat(),
            "full_universe_symbols": ["2317"],
            "execution_symbols": ["2317"],
            "status": "ready",
        }

    monkeypatch.setattr(module, "valid_successful_cohort_runs", existing_runs)
    monkeypatch.setattr(module, "preflight_cohort", preflight)
    monkeypatch.setattr(
        module,
        "create_research_run",
        lambda request, **kwargs: SimpleNamespace(run_id=kwargs["run_id"]),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tw_prospective_cohorts.py",
            "--basis-date",
            basis_date.isoformat(),
        ],
    )

    with caplog.at_level("ERROR"):
        assert module.main() == 1

    reports = json.loads(capsys.readouterr().out)["cohorts"]
    assert reports[0] == {
        "cohort_id": module.COHORT_2330,
        "basis_date": basis_date.isoformat(),
        "status": "error",
        "failure_kind": "DataAccessError",
        "reason": "research registry unavailable",
    }
    assert reports[1]["status"] == "created"
    assert "cohort_id=tw_2330_o2o_v1" in caplog.text
