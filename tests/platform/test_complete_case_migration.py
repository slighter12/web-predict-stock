import importlib

import pytest
import sqlalchemy as sa


def test_complete_case_policy_migration_upgrade_and_rejects_downgrade(monkeypatch):
    migration = importlib.import_module(
        "backend.alembic.versions.0009_complete_case_model_inputs"
    )
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    research_runs = sa.Table(
        "research_runs",
        metadata,
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("missing_feature_policy_version", sa.String()),
        sa.Column("missing_feature_policy_state", sa.String()),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            research_runs.insert(),
            [
                {
                    "run_id": "legacy-native",
                    "missing_feature_policy_version": "xgboost_native_missing_v1",
                    "missing_feature_policy_state": "native_missing_supported",
                },
                {
                    "run_id": "legacy-filtered",
                    "missing_feature_policy_version": "xgboost_native_missing_v1",
                    "missing_feature_policy_state": "core_data_gaps_filtered",
                },
                {
                    "run_id": "unrelated",
                    "missing_feature_policy_version": "other_policy_v1",
                    "missing_feature_policy_state": "feature_complete",
                },
            ],
        )
        monkeypatch.setattr(migration.op, "execute", connection.execute)

        migration.upgrade()

        rows = {
            row.run_id: row
            for row in connection.execute(sa.select(research_runs)).all()
        }
        for run_id in ("legacy-native", "legacy-filtered"):
            assert (
                rows[run_id].missing_feature_policy_version
                == "complete_case_model_inputs_v1"
            )
            assert rows[run_id].missing_feature_policy_state == "complete_case_applied"
        assert rows["unrelated"].missing_feature_policy_version == "other_policy_v1"
        assert rows["unrelated"].missing_feature_policy_state == "feature_complete"

        execute_calls = 0

        def _unexpected_execute(statement):
            nonlocal execute_calls
            execute_calls += 1
            return connection.execute(statement)

        monkeypatch.setattr(migration.op, "execute", _unexpected_execute)
        with pytest.raises(
            RuntimeError,
            match="cannot safely restore legacy missing-feature labels",
        ):
            migration.downgrade()

        rows = {
            row.run_id: row
            for row in connection.execute(sa.select(research_runs)).all()
        }
        for run_id in ("legacy-native", "legacy-filtered"):
            assert (
                rows[run_id].missing_feature_policy_version
                == "complete_case_model_inputs_v1"
            )
            assert rows[run_id].missing_feature_policy_state == "complete_case_applied"
        assert execute_calls == 0
        assert rows["unrelated"].missing_feature_policy_version == "other_policy_v1"
        assert rows["unrelated"].missing_feature_policy_state == "feature_complete"
