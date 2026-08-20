import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def _load_calibration_migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "alembic"
        / "versions"
        / "0009_calibration_matrices.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load migration from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calibration_migration_downgrade_preserves_evidence():
    migration = _load_calibration_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        connection.execute(
            text(
                "INSERT INTO calibration_matrices "
                "(matrix_id, request_id, status, request_payload_json, result_payload_json) "
                "VALUES ('matrix_1', 'request_1', 'succeeded', '{}', '{}')"
            )
        )

        with Operations.context(context):
            migration.downgrade()

        assert inspect(connection).has_table("calibration_matrices")
        assert (
            connection.execute(
                text(
                    "SELECT matrix_id FROM calibration_matrices "
                    "WHERE matrix_id = 'matrix_1'"
                )
            ).scalar_one()
            == "matrix_1"
        )
