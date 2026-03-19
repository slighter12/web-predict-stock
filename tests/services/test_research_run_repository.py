from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.repositories.research_run_repository as research_run_repository
from backend.database import Base, ResearchRun
from backend.domain.runtime_bundle import build_version_pack_payload


def test_research_run_repository_roundtrip(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[ResearchRun.__table__])
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
        **build_version_pack_payload(
            {
                "threshold_policy_version": "static_absolute_gross_label_v1",
                "price_basis_version": "label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
                "benchmark_comparability_gate": False,
                "comparison_eligibility": "comparison_metadata_only",
            }
        ),
    }

    research_run_repository.persist_research_run_record(payload)
    loaded = research_run_repository.get_research_run_record("run_123")

    assert loaded["run_id"] == "run_123"
    assert loaded["effective_strategy"] == {"threshold": 0.003, "top_n": 3}
    assert loaded["comparison_eligibility"] == "comparison_metadata_only"
    assert loaded["version_pack_status"]["adv_basis_version"] == "placeholder"
