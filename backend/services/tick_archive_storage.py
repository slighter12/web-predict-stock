from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

_ARCHIVE_ROOT = Path(__file__).resolve().parents[2] / "var" / "tick_archives"


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
    directory = path.parent
    project_root = Path(__file__).resolve().parents[2]
    while directory != project_root and directory.exists():
        try:
            directory.rmdir()
        except OSError:
            break
        directory = directory.parent
    return True
