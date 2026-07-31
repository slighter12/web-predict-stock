from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class LatestSignalSelection:
    latest: list[Mapping[str, Any]]
    invalid_row_count: int
    unexpected_symbols: list[str]
    snapshot_complete: bool


def signal_date_key(signal: Mapping[str, Any]) -> str | None:
    value = signal.get("date")
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return None
    return None


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_probability(value: Any) -> bool:
    return _is_number(value) and 0.0 <= value <= 1.0


def select_latest_signals(
    payload: Mapping[str, Any],
) -> LatestSignalSelection:
    declared = _as_list(payload.get("symbols")) or _as_list(
        _as_mapping(payload.get("request_payload")).get("symbols")
    )
    allowed_symbols = {str(symbol) for symbol in declared if symbol}
    forward_by_symbol: dict[
        str, tuple[str, list[tuple[int, Mapping[str, Any]]]]
    ] = {}
    invalid_row_indices: set[int] = set()
    unexpected_symbols: set[str] = set()
    for row_index, item in enumerate(_as_list(payload.get("signals"))):
        signal = _as_mapping(item)
        if signal.get("signal_kind") != "forward_opinion":
            continue
        symbol = signal.get("symbol")
        if not symbol:
            invalid_row_indices.add(row_index)
            continue
        symbol_key = str(symbol)
        if symbol_key not in allowed_symbols:
            unexpected_symbols.add(symbol_key)
            invalid_row_indices.add(row_index)
            continue
        signal_date = signal_date_key(signal)
        if signal_date is None:
            invalid_row_indices.add(row_index)
            continue
        current = forward_by_symbol.get(symbol_key)
        if current is None or signal_date > current[0]:
            forward_by_symbol[symbol_key] = (
                signal_date,
                [(row_index, signal)],
            )
        elif signal_date == current[0]:
            current[1].append((row_index, signal))

    forward_dates = {selection[0] for selection in forward_by_symbol.values()}
    common_as_of = max(forward_dates) if forward_dates else None
    latest: list[Mapping[str, Any]] = []
    for symbol in sorted(forward_by_symbol):
        signal_date, candidates = forward_by_symbol[symbol]
        selected_index, selected_signal = candidates[0]
        latest.append(selected_signal)
        invalid_row_indices.update(index for index, _ in candidates[1:])
        if signal_date != common_as_of:
            invalid_row_indices.add(selected_index)
        if (
            not _is_number(selected_signal.get("score"))
            or not _is_number(selected_signal.get("position"))
            or not _is_probability(selected_signal.get("up_probability"))
            or selected_signal.get("predicted_direction") not in {"up", "down"}
        ):
            invalid_row_indices.add(selected_index)

    snapshot_complete = (
        bool(allowed_symbols)
        and set(forward_by_symbol) == allowed_symbols
        and len(forward_dates) == 1
        and all(len(candidates) == 1 for _, candidates in forward_by_symbol.values())
        and not invalid_row_indices
    )
    return LatestSignalSelection(
        latest=latest,
        invalid_row_count=len(invalid_row_indices),
        unexpected_symbols=sorted(unexpected_symbols),
        snapshot_complete=snapshot_complete,
    )


def valid_latest_signals(
    payload: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    return [
        item
        for item in select_latest_signals(payload).latest
        if signal_date_key(item) is not None
        and _is_number(item.get("score"))
        and _is_number(item.get("position"))
        and _is_probability(item.get("up_probability"))
        and item.get("predicted_direction") in {"up", "down"}
    ]
