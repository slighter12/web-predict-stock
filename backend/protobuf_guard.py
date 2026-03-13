from __future__ import annotations

from typing import Any


class _DepthLimitExceeded(Exception):
    pass


_PARSE_DICT_GUARDED = False


def _ensure_max_depth(value: Any, limit: int) -> None:
    if limit < 0:
        return

    stack: list[tuple[Any, int]] = [(value, 0)]
    seen: set[int] = set()

    while stack:
        current, depth = stack.pop()
        if depth > limit:
            raise _DepthLimitExceeded(f"JSON max recursion depth exceeded ({limit}).")

        if isinstance(current, dict):
            obj_id = id(current)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            obj_id = id(current)
            if obj_id in seen:
                continue
            seen.add(obj_id)
            stack.extend((item, depth + 1) for item in current)


def install_protobuf_json_guard() -> None:
    global _PARSE_DICT_GUARDED
    if _PARSE_DICT_GUARDED:
        return

    try:
        from google.protobuf import json_format as _json_format
    except Exception:
        return

    original_parse = getattr(_json_format, "ParseDict", None)
    if original_parse is None:
        return

    default_depth = None
    defaults = getattr(original_parse, "__defaults__", None)
    if defaults:
        candidate = defaults[-1]
        if isinstance(candidate, int):
            default_depth = candidate
    if default_depth is None:
        candidate = getattr(_json_format, "_DEFAULT_MAX_RECURSION_DEPTH", 100)
        default_depth = candidate if isinstance(candidate, int) else 100

    def _guarded_parse_dict(
        js_dict: dict,
        message: Any,
        ignore_unknown_fields: bool = False,
        descriptor_pool: Any | None = None,
        max_recursion_depth: int | None = None,
    ) -> Any:
        depth_limit = (
            default_depth if max_recursion_depth is None else max_recursion_depth
        )
        if depth_limit is not None:
            try:
                _ensure_max_depth(js_dict, depth_limit)
            except _DepthLimitExceeded as exc:
                parse_error = getattr(_json_format, "ParseError", ValueError)
                raise parse_error(str(exc)) from exc
        return original_parse(
            js_dict,
            message,
            ignore_unknown_fields=ignore_unknown_fields,
            descriptor_pool=descriptor_pool,
            max_recursion_depth=depth_limit,
        )

    _json_format.ParseDict = _guarded_parse_dict
    _PARSE_DICT_GUARDED = True
