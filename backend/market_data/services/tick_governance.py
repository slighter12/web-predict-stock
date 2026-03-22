from __future__ import annotations

from sqlalchemy import func, select

from backend.database import (
    SessionLocal,
    TickArchiveObject,
    TickArchiveRun,
    TickObservation,
    TickRestoreRun,
)
from backend.market_data.services.tick_archive_storage import archive_object_exists
from backend.market_data.services.tick_archives import (
    TICK_ARCHIVE_LAYOUT_VERSION,
    TICK_ARCHIVE_RETENTION_CLASS,
)
from backend.platform.errors import DataAccessError

_SUCCEEDED_STATUS = "succeeded"
_RESTORE_TEMP_RETENTION_DAYS = 7
_RAW_ARCHIVE_RETENTION_DAYS = 365


def _artifact(status: str, details: dict) -> dict:
    return {"status": status, "details": details}


def get_tick_phase_gate_summary() -> dict:
    try:
        with SessionLocal() as session:
            latest_archive_object = (
                session.execute(
                    select(TickArchiveObject)
                    .join(TickArchiveRun, TickArchiveRun.id == TickArchiveObject.run_id)
                    .where(TickArchiveRun.status == _SUCCEEDED_STATUS)
                    .order_by(
                        TickArchiveObject.created_at.desc(), TickArchiveObject.id.desc()
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            succeeded_restore_count = (
                session.scalar(
                    select(func.count())
                    .select_from(TickRestoreRun)
                    .where(TickRestoreRun.restore_status == _SUCCEEDED_STATUS)
                )
                or 0
            )
    except Exception as exc:
        raise DataAccessError("Failed to evaluate tick phase gate summary.") from exc

    latest_archive_restore_run = None
    latest_archive_observation_count = 0
    latest_archive_object_reference: str | None = None
    archive_exists = False
    archive_exists_error: str | None = None

    if latest_archive_object is not None:
        try:
            archive_exists = archive_object_exists(
                object_key=latest_archive_object.object_key,
                storage_backend=latest_archive_object.storage_backend,
            )
        except ValueError as exc:
            archive_exists_error = str(exc)
        try:
            with SessionLocal() as session:
                latest_archive_restore_run = (
                    session.execute(
                        select(TickRestoreRun)
                        .where(
                            TickRestoreRun.archive_object_id == latest_archive_object.id
                        )
                        .order_by(
                            TickRestoreRun.created_at.desc(),
                            TickRestoreRun.id.desc(),
                        )
                        .limit(1)
                    )
                    .scalars()
                    .first()
                )
                latest_archive_object_reference = (
                    f"tick_archive_object:{latest_archive_object.id}"
                )
                latest_archive_observation_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(TickObservation)
                        .where(
                            TickObservation.archive_object_reference
                            == latest_archive_object_reference
                        )
                    )
                    or 0
                )
        except Exception as exc:
            raise DataAccessError(
                "Failed to evaluate tick phase gate summary."
            ) from exc

    raw_archive_status = (
        "pass" if latest_archive_object is not None and archive_exists else "fail"
    )
    replay_status = (
        "pass"
        if latest_archive_object is not None
        and latest_archive_restore_run is not None
        and latest_archive_restore_run.restore_status == _SUCCEEDED_STATUS
        and latest_archive_observation_count > 0
        else "fail"
    )
    metadata_status = "pass" if latest_archive_object is not None else "fail"
    telemetry_status = (
        "pass"
        if latest_archive_object is not None
        and latest_archive_restore_run is not None
        and latest_archive_restore_run.restore_status == _SUCCEEDED_STATUS
        and latest_archive_restore_run.elapsed_seconds is not None
        and latest_archive_restore_run.throughput_gb_per_minute is not None
        else "fail"
    )
    retention_status = (
        "pass"
        if latest_archive_object is not None
        and latest_archive_object.retention_class == TICK_ARCHIVE_RETENTION_CLASS
        and latest_archive_object.archive_layout_version == TICK_ARCHIVE_LAYOUT_VERSION
        else "fail"
    )

    artifacts = {
        "raw_tick_archive": _artifact(
            raw_archive_status,
            {
                "latest_archive_object_id": latest_archive_object.id
                if latest_archive_object is not None
                else None,
                "object_key": latest_archive_object.object_key
                if latest_archive_object is not None
                else None,
                "storage_backend": latest_archive_object.storage_backend
                if latest_archive_object is not None
                else None,
                "path_exists": archive_exists,
                "existence_check_error": archive_exists_error,
            },
        ),
        "normalized_replay_path": _artifact(
            replay_status,
            {
                "latest_archive_object_id": latest_archive_object.id
                if latest_archive_object is not None
                else None,
                "latest_restore_run_id": latest_archive_restore_run.id
                if latest_archive_restore_run is not None
                else None,
                "latest_restore_status": latest_archive_restore_run.restore_status
                if latest_archive_restore_run is not None
                else None,
                "latest_archive_object_reference": latest_archive_object_reference,
                "latest_replay_observation_count": int(
                    latest_archive_observation_count
                ),
            },
        ),
        "archive_metadata": _artifact(
            metadata_status,
            {
                "latest_archive_layout_version": latest_archive_object.archive_layout_version
                if latest_archive_object is not None
                else None,
                "latest_retention_class": latest_archive_object.retention_class
                if latest_archive_object is not None
                else None,
                "latest_checksum_present": bool(latest_archive_object.checksum)
                if latest_archive_object is not None
                else False,
            },
        ),
        "retention_policy": _artifact(
            retention_status,
            {
                "raw_archive_retention_days": _RAW_ARCHIVE_RETENTION_DAYS,
                "restore_temp_retention_days": _RESTORE_TEMP_RETENTION_DAYS,
                "latest_archive_object_id": latest_archive_object.id
                if latest_archive_object is not None
                else None,
                "expected_retention_class": TICK_ARCHIVE_RETENTION_CLASS,
                "actual_retention_class": latest_archive_object.retention_class
                if latest_archive_object is not None
                else None,
                "expected_archive_layout_version": TICK_ARCHIVE_LAYOUT_VERSION,
                "actual_archive_layout_version": latest_archive_object.archive_layout_version
                if latest_archive_object is not None
                else None,
            },
        ),
        "restore_telemetry": _artifact(
            telemetry_status,
            {
                "succeeded_restore_run_count": int(succeeded_restore_count),
                "latest_archive_object_id": latest_archive_object.id
                if latest_archive_object is not None
                else None,
                "latest_restore_run_id": latest_archive_restore_run.id
                if latest_archive_restore_run is not None
                else None,
                "latest_restore_status": latest_archive_restore_run.restore_status
                if latest_archive_restore_run is not None
                else None,
                "latest_elapsed_seconds": latest_archive_restore_run.elapsed_seconds
                if latest_archive_restore_run is not None
                else None,
                "latest_throughput_gb_per_minute": latest_archive_restore_run.throughput_gb_per_minute
                if latest_archive_restore_run is not None
                else None,
                "requires_elapsed_seconds": True,
                "requires_throughput_gb_per_minute": True,
            },
        ),
    }
    overall_status = (
        "pass"
        if all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P2-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "artifacts": artifacts,
    }
