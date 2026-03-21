from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

_ARCHIVE_ROOT = Path(__file__).resolve().parents[2] / "var" / "tick_archives"
_GOOGLE_DRIVE_ROOT_ENV = "GOOGLE_DRIVE_TICK_ARCHIVE_ROOT"
_GOOGLE_DRIVE_BACKUP_PREFIX = "google_drive_mirror"


def _run_directory(market: str, trading_date: date, run_id: int) -> Path:
    return _ARCHIVE_ROOT / market / trading_date.isoformat() / str(run_id)


def _gzip_bytes(lines: list[str]) -> tuple[bytes, int]:
    raw_bytes = "".join(lines).encode("utf-8")
    return gzip.compress(raw_bytes), len(raw_bytes)


def write_archive_part(
    *,
    market: str,
    trading_date: date,
    run_id: int,
    part_number: int,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    directory = _run_directory(market, trading_date, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    file_name = f"part-{part_number:05d}.jsonl.gz"
    path = directory / file_name
    lines = [
        json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n" for entry in entries
    ]
    compressed_bytes, uncompressed_bytes = _gzip_bytes(lines)
    path.write_bytes(compressed_bytes)
    return _build_file_metadata(path, compressed_bytes, uncompressed_bytes)


def write_uploaded_archive(
    *,
    market: str,
    trading_date: date,
    run_id: int,
    file_bytes: bytes,
) -> dict[str, Any]:
    directory = _run_directory(market, trading_date, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "part-00001.jsonl.gz"
    try:
        gzip.decompress(file_bytes)
        compressed_bytes = file_bytes
        uncompressed_bytes = len(gzip.decompress(file_bytes))
    except OSError:
        compressed_bytes = gzip.compress(file_bytes)
        uncompressed_bytes = len(file_bytes)
    path.write_bytes(compressed_bytes)
    return _build_file_metadata(path, compressed_bytes, uncompressed_bytes)


def _build_file_metadata(
    path: Path, compressed_bytes: bytes, uncompressed_bytes: int
) -> dict[str, Any]:
    relative_path = path.relative_to(Path(__file__).resolve().parents[2]).as_posix()
    compression_ratio = (
        max(0.0, 1 - (len(compressed_bytes) / uncompressed_bytes))
        if uncompressed_bytes > 0
        else 0.0
    )
    return {
        "object_key": relative_path,
        "compressed_bytes": len(compressed_bytes),
        "uncompressed_bytes": uncompressed_bytes,
        "compression_ratio": compression_ratio,
        "checksum": hashlib.sha256(compressed_bytes).hexdigest(),
    }


def _google_drive_backup_object_key(object_key: str) -> str:
    return f"{_GOOGLE_DRIVE_BACKUP_PREFIX}/{object_key}"


def _google_drive_root() -> Path | None:
    drive_root = os.getenv(_GOOGLE_DRIVE_ROOT_ENV)
    if not drive_root:
        return None
    return Path(drive_root).expanduser().resolve()


def _cleanup_empty_parent_directories(path: Path, *, stop_at: Path) -> None:
    directory = path.parent
    while directory != stop_at and directory.exists():
        try:
            directory.rmdir()
        except OSError:
            break
        directory = directory.parent


def _ensure_path_within_root(path: Path, *, root: Path) -> Path:
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid object key: path traversal detected.") from exc
    return resolved_path


def _backup_object_key_to_google_drive_path(backup_object_key: str) -> Path:
    if not backup_object_key.startswith(f"{_GOOGLE_DRIVE_BACKUP_PREFIX}/"):
        raise ValueError(
            f"Unsupported Google Drive backup object key: {backup_object_key}"
        )
    drive_root = _google_drive_root()
    if drive_root is None:
        raise ValueError(
            "GOOGLE_DRIVE_TICK_ARCHIVE_ROOT is required to manage archive mirrors."
        )
    relative_object_key = backup_object_key.removeprefix(
        f"{_GOOGLE_DRIVE_BACKUP_PREFIX}/"
    )
    return _ensure_path_within_root(drive_root / relative_object_key, root=drive_root)


def mirror_archive_to_google_drive(*, object_key: str) -> dict[str, Any]:
    drive_root = _google_drive_root()
    if drive_root is None:
        return {
            "backup_backend": "google_drive_mirror",
            "backup_object_key": None,
            "backup_status": "not_configured",
            "backup_completed_at": None,
            "backup_error": None,
        }

    source_path = object_key_to_path(object_key)
    destination_path = _ensure_path_within_root(drive_root / object_key, root=drive_root)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    source_checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
    destination_checksum = hashlib.sha256(destination_path.read_bytes()).hexdigest()
    if source_checksum != destination_checksum:
        destination_path.unlink(missing_ok=True)
        raise ValueError("Google Drive mirror checksum mismatch.")
    return {
        "backup_backend": "google_drive_mirror",
        "backup_object_key": _google_drive_backup_object_key(object_key),
        "backup_status": "succeeded",
        "backup_completed_at": datetime.now().astimezone(),
        "backup_error": None,
    }


def delete_google_drive_archive_mirror(*, backup_object_key: str) -> bool:
    drive_root = _google_drive_root()
    if drive_root is None:
        raise ValueError(
            "GOOGLE_DRIVE_TICK_ARCHIVE_ROOT is required to manage archive mirrors."
        )
    destination_path = _backup_object_key_to_google_drive_path(backup_object_key)
    if not destination_path.exists():
        return False
    destination_path.unlink()
    _cleanup_empty_parent_directories(destination_path, stop_at=drive_root)
    return True


def read_archive_entries(object_key: str) -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / object_key
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def object_key_to_path(object_key: str) -> Path:
    return Path(__file__).resolve().parents[2] / object_key


def archive_object_exists(*, object_key: str, storage_backend: str) -> bool:
    if storage_backend == "local_filesystem":
        return object_key_to_path(object_key).exists()
    raise ValueError(f"Unsupported tick archive storage backend: {storage_backend}")


def delete_archive_object(*, object_key: str, storage_backend: str) -> bool:
    if storage_backend != "local_filesystem":
        raise ValueError(f"Unsupported tick archive storage backend: {storage_backend}")
    path = object_key_to_path(object_key)
    if not path.exists():
        return False
    path.unlink()
    project_root = Path(__file__).resolve().parents[2]
    _cleanup_empty_parent_directories(path, stop_at=project_root)
    return True
