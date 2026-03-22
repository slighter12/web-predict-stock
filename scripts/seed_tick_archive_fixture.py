from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from sqlalchemy import delete, select

from backend.database import (
    SessionLocal,
    TickArchiveObject,
    TickArchiveRun,
    TickObservation,
    TickRestoreRun,
)
from backend.market_data.repositories.benchmark_profiles import (
    persist_benchmark_profile,
)
from backend.market_data.repositories.tick_archives import (
    list_recent_tick_archive_trading_dates,
    list_tick_archive_objects_for_dates,
    list_tick_restore_runs_for_dates,
    persist_tick_archive_object,
    persist_tick_archive_run,
)
from backend.market_data.services.tick_archive_provider import (
    TWSE_PUBLIC_SNAPSHOT_SOURCE,
    parse_archive_entry,
)
from backend.market_data.services.tick_archive_storage import (
    object_key_to_path,
    write_archive_part,
)
from backend.market_data.services.tick_archives import (
    TICK_ARCHIVE_LAYOUT_VERSION,
    TICK_ARCHIVE_RETENTION_CLASS,
    TICK_COMPRESSION_CODEC,
    TICK_STORAGE_BACKEND,
)
from backend.market_data.services.tick_governance import get_tick_phase_gate_summary
from backend.market_data.services.tick_ops import get_tick_ops_kpi_summary
from backend.market_data.services.tick_replay import create_tick_replay
from backend.platform.time import utc_now

FIXTURE_NOTES_PREFIX = "[tick-p2-acceptance-fixture]"
FIXTURE_PROFILE_ID = "tick_p2_acceptance_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARTIAL_DAY = date(2099, 1, 2)
FULL_DAY = date(2099, 1, 3)
FAILED_DAY = date(2099, 1, 4)
FIXTURE_DATES = (PARTIAL_DAY, FULL_DAY, FAILED_DAY)


def _build_snapshot_payload(
    *,
    symbols: list[str],
    trading_date: date,
    price_offset: int,
) -> str:
    items: list[dict[str, str]] = []
    base_dt = datetime.combine(
        trading_date,
        time(hour=13, minute=30),
        tzinfo=timezone.utc,
    )
    for index, symbol in enumerate(symbols):
        price = 1000.0 + price_offset + index * 10
        items.append(
            {
                "c": symbol,
                "d": trading_date.strftime("%Y%m%d"),
                "tlong": str(int(base_dt.timestamp() * 1000) + index * 1000),
                "z": f"{price:.4f}",
                "tv": str(100 + index),
                "v": str(1000 + index * 100),
                "a": f"{price + 1:.4f}_{price + 2:.4f}_",
                "f": "10_20_",
                "b": f"{price:.4f}_{price - 1:.4f}_",
                "g": "30_40_",
            }
        )
    return json.dumps({"msgArray": items}, ensure_ascii=True, sort_keys=True)


def _make_archive_entry(
    *,
    trading_date: date,
    symbols: list[str],
    part_number: int,
    price_offset: int,
) -> dict:
    fetch_timestamp = datetime.combine(
        trading_date,
        time(hour=7, minute=5 + part_number),
        tzinfo=timezone.utc,
    )
    return {
        "source_name": TWSE_PUBLIC_SNAPSHOT_SOURCE,
        "market": "TW",
        "fetch_timestamp": fetch_timestamp.isoformat(),
        "request_symbols": list(symbols),
        "request_url": f"https://fixture.local/tick/{trading_date.isoformat()}/part-{part_number:05d}",
        "response_status": 200,
        "raw_response_body": _build_snapshot_payload(
            symbols=symbols,
            trading_date=trading_date,
            price_offset=price_offset,
        ),
    }


def _base_run_payload(*, trading_date: date, label: str, status: str) -> dict:
    now = utc_now()
    return {
        "source_name": TWSE_PUBLIC_SNAPSHOT_SOURCE,
        "market": "TW",
        "trading_date": trading_date,
        "trigger_mode": "post_close_crawl",
        "scope": "full_market",
        "status": status,
        "notes": f"{FIXTURE_NOTES_PREFIX} {label}",
        "symbol_count": 0,
        "request_count": 0,
        "observation_count": 0,
        "started_at": now,
        "completed_at": now,
        "abort_reason": None if status == "succeeded" else "fixture failed run",
    }


def _archive_object_payload(
    *,
    run_id: int,
    file_metadata: dict,
    observations: list[dict],
) -> dict:
    observation_ts_values = [item["observation_ts"] for item in observations]
    return {
        "run_id": run_id,
        "storage_backend": TICK_STORAGE_BACKEND,
        "object_key": file_metadata["object_key"],
        "compression_codec": TICK_COMPRESSION_CODEC,
        "archive_layout_version": TICK_ARCHIVE_LAYOUT_VERSION,
        "compressed_bytes": file_metadata["compressed_bytes"],
        "uncompressed_bytes": file_metadata["uncompressed_bytes"],
        "compression_ratio": file_metadata["compression_ratio"],
        "record_count": len(observations),
        "first_observation_ts": min(observation_ts_values)
        if observation_ts_values
        else None,
        "last_observation_ts": max(observation_ts_values)
        if observation_ts_values
        else None,
        "checksum": file_metadata["checksum"],
        "retention_class": TICK_ARCHIVE_RETENTION_CLASS,
    }


def _ensure_benchmark_profile() -> dict:
    return persist_benchmark_profile(
        {
            "id": FIXTURE_PROFILE_ID,
            "cpu_class": "fixture_cpu_standard",
            "memory_size": "16GB",
            "storage_type": "local_ssd",
            "compression_settings": "gzip_default",
            "archive_layout_version": TICK_ARCHIVE_LAYOUT_VERSION,
            "network_class": "local_only",
        }
    )


def _cleanup_fixture_data() -> dict:
    removed_paths: list[str] = []
    with SessionLocal() as session:
        run_rows = (
            session.execute(
                select(TickArchiveRun).where(
                    TickArchiveRun.trading_date.in_(FIXTURE_DATES),
                    TickArchiveRun.notes.like(f"{FIXTURE_NOTES_PREFIX}%"),
                )
            )
            .scalars()
            .all()
        )
        run_ids = [row.id for row in run_rows]
        object_rows = (
            session.execute(
                select(TickArchiveObject).where(TickArchiveObject.run_id.in_(run_ids))
            )
            .scalars()
            .all()
            if run_ids
            else []
        )
        object_ids = [row.id for row in object_rows]
        object_refs = [f"tick_archive_object:{row.id}" for row in object_rows]
        object_paths = [object_key_to_path(row.object_key) for row in object_rows]

        if object_ids:
            session.execute(
                delete(TickRestoreRun).where(
                    TickRestoreRun.archive_object_id.in_(object_ids)
                )
            )
        if object_refs:
            session.execute(
                delete(TickObservation).where(
                    TickObservation.archive_object_reference.in_(object_refs)
                )
            )
        if object_ids:
            session.execute(
                delete(TickArchiveObject).where(TickArchiveObject.id.in_(object_ids))
            )
        if run_ids:
            session.execute(
                delete(TickArchiveRun).where(TickArchiveRun.id.in_(run_ids))
            )
        session.commit()

    for path in object_paths:
        if path.exists():
            path.unlink()
            removed_paths.append(str(path))
            directory = path.parent
            while directory != PROJECT_ROOT and directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    break
                directory = directory.parent
    return {
        "removed_run_count": len(run_ids),
        "removed_object_count": len(object_rows),
        "removed_paths": removed_paths,
    }


def _create_fixture_run(
    *,
    trading_date: date,
    label: str,
    status: str,
    symbol_groups: list[list[str]],
) -> dict:
    run = persist_tick_archive_run(
        _base_run_payload(trading_date=trading_date, label=label, status=status)
    )
    archive_objects: list[dict] = []
    total_symbols = 0
    total_observations = 0

    for part_number, symbols in enumerate(symbol_groups, start=1):
        entry = _make_archive_entry(
            trading_date=trading_date,
            symbols=symbols,
            part_number=part_number,
            price_offset=part_number * 10,
        )
        file_metadata = write_archive_part(
            market="TW",
            trading_date=trading_date,
            run_id=run["id"],
            part_number=part_number,
            entries=[entry],
        )
        observations = parse_archive_entry(entry)
        archive_objects.append(
            persist_tick_archive_object(
                _archive_object_payload(
                    run_id=run["id"],
                    file_metadata=file_metadata,
                    observations=observations,
                )
            )
        )
        total_symbols += len(symbols)
        total_observations += len(observations)

    run.update(
        {
            "symbol_count": total_symbols,
            "request_count": len(symbol_groups),
            "observation_count": total_observations,
        }
    )
    run = persist_tick_archive_run(run)
    return {"run": run, "archive_objects": archive_objects}


def _seed_fixture() -> dict:
    _ensure_benchmark_profile()
    partial_fixture = _create_fixture_run(
        trading_date=PARTIAL_DAY,
        label="partial-day",
        status="succeeded",
        symbol_groups=[["2330"], ["2317"]],
    )
    full_fixture = _create_fixture_run(
        trading_date=FULL_DAY,
        label="full-day",
        status="succeeded",
        symbol_groups=[["2603"], ["2881"]],
    )
    failed_fixture = _create_fixture_run(
        trading_date=FAILED_DAY,
        label="failed-day",
        status="failed",
        symbol_groups=[["1101"], ["1216"]],
    )

    partial_replays = [
        create_tick_replay(
            archive_object_id=partial_fixture["archive_objects"][0]["id"],
            benchmark_profile_id=FIXTURE_PROFILE_ID,
            notes=f"{FIXTURE_NOTES_PREFIX} partial replay only",
        )
    ]
    full_replays = [
        create_tick_replay(
            archive_object_id=archive_object["id"],
            benchmark_profile_id=FIXTURE_PROFILE_ID,
            notes=f"{FIXTURE_NOTES_PREFIX} full replay",
        )
        for archive_object in full_fixture["archive_objects"]
    ]
    failed_replays = [
        create_tick_replay(
            archive_object_id=archive_object["id"],
            benchmark_profile_id=FIXTURE_PROFILE_ID,
            notes=f"{FIXTURE_NOTES_PREFIX} failed-run replay",
        )
        for archive_object in failed_fixture["archive_objects"]
    ]
    return {
        "partial_fixture": partial_fixture,
        "full_fixture": full_fixture,
        "failed_fixture": failed_fixture,
        "partial_replays": partial_replays,
        "full_replays": full_replays,
        "failed_replays": failed_replays,
    }


def _assertions(summary: dict) -> list[dict]:
    kpis = summary["kpi_summary"]
    gate = summary["gate_summary"]
    successful_trading_dates = summary["repository_window"]["successful_trading_dates"]
    assertions = [
        {
            "name": "failed_run_excluded_from_trading_dates",
            "passed": FAILED_DAY.isoformat() not in successful_trading_dates,
            "details": {"successful_trading_dates": successful_trading_dates},
        },
        {
            "name": "partial_day_excluded_from_benchmark_window",
            "passed": kpis["metrics"]["KPI-TICK-002"]["details"][
                "eligible_window_count"
            ]
            == 1,
            "details": kpis["metrics"]["KPI-TICK-002"]["details"],
        },
        {
            "name": "throughput_uses_same_single_window",
            "passed": kpis["metrics"]["KPI-TICK-003"]["details"]["sample_count"] == 1,
            "details": kpis["metrics"]["KPI-TICK-003"]["details"],
        },
        {
            "name": "selection_policy_persists_5gb_rule",
            "passed": kpis["selection_policy"]["max_compressed_gb_per_trading_day"]
            == 5.0,
            "details": kpis["selection_policy"],
        },
        {
            "name": "gate_p2_artifacts_present",
            "passed": gate["overall_status"] == "pass",
            "details": gate["artifacts"],
        },
    ]
    return assertions


def run_acceptance(*, cleanup_after: bool) -> dict:
    cleanup_summary = _cleanup_fixture_data()
    seeded = _seed_fixture()
    successful_trading_dates = [
        item.isoformat()
        for item in list_recent_tick_archive_trading_dates(
            limit=20,
            statuses=["succeeded"],
        )
    ]
    succeeded_dates = [PARTIAL_DAY, FULL_DAY]
    repository_window = {
        "successful_trading_dates": successful_trading_dates,
        "archive_object_count": len(
            list_tick_archive_objects_for_dates(
                succeeded_dates,
                run_statuses=["succeeded"],
            )
        ),
        "restore_run_count": len(
            list_tick_restore_runs_for_dates(
                succeeded_dates,
                benchmark_only=True,
                archive_run_statuses=["succeeded"],
                restore_statuses=["succeeded"],
            )
        ),
    }
    summary = {
        "cleanup_summary": cleanup_summary,
        "benchmark_profile_id": FIXTURE_PROFILE_ID,
        "seeded": {
            "partial_run_id": seeded["partial_fixture"]["run"]["id"],
            "full_run_id": seeded["full_fixture"]["run"]["id"],
            "failed_run_id": seeded["failed_fixture"]["run"]["id"],
            "partial_archive_object_ids": [
                item["id"] for item in seeded["partial_fixture"]["archive_objects"]
            ],
            "full_archive_object_ids": [
                item["id"] for item in seeded["full_fixture"]["archive_objects"]
            ],
            "failed_archive_object_ids": [
                item["id"] for item in seeded["failed_fixture"]["archive_objects"]
            ],
        },
        "repository_window": repository_window,
        "kpi_summary": get_tick_ops_kpi_summary(),
        "gate_summary": get_tick_phase_gate_summary(),
    }
    summary["assertions"] = _assertions(summary)
    summary["all_passed"] = all(item["passed"] for item in summary["assertions"])

    if cleanup_after:
        summary["cleanup_after_summary"] = _cleanup_fixture_data()

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed deterministic P2 tick-archive fixtures and verify Stage 2 gate behavior.",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Remove existing acceptance fixtures and exit.",
    )
    parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Delete seeded fixtures after the verification run completes.",
    )
    args = parser.parse_args()

    if args.cleanup_only:
        print(json.dumps(_cleanup_fixture_data(), ensure_ascii=True, indent=2))
        return 0

    summary = run_acceptance(cleanup_after=args.cleanup_after)
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
