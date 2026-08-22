from __future__ import annotations

from collections.abc import Sequence

from backend.platform.errors import UnsupportedConfigurationError
from backend.research.contracts.runs import FeatureSpec
from backend.shared.analytics import features as feature_engine


def build_feature_config(
    features: Sequence[FeatureSpec],
    *,
    require_nonempty: bool = False,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, int]]:
    """Validate Feature Specs and build the engine config plus shift map."""
    if require_nonempty and not features:
        raise UnsupportedConfigurationError(
            "features must include at least one feature spec."
        )

    config: dict[str, list[dict[str, object]]] = {}
    shift_map: dict[str, int] = {}
    for spec in features:
        try:
            feature_engine.validate_feature_config_entry(
                spec.name,
                window=spec.window,
                source=spec.source,
            )
        except ValueError as exc:
            raise UnsupportedConfigurationError(str(exc)) from exc

        config.setdefault(spec.name, []).append(
            {"window": spec.window, "source": spec.source}
        )
        column_name = feature_engine.feature_col_name(
            spec.name,
            spec.window,
            spec.source,
        )
        previous_shift = shift_map.get(column_name)
        if previous_shift is not None and previous_shift != spec.shift:
            raise UnsupportedConfigurationError(
                f"Feature '{column_name}' has conflicting shift values: "
                f"{previous_shift} and {spec.shift}."
            )
        shift_map[column_name] = spec.shift

    for feature_name, items in config.items():
        try:
            unique = {(item["window"], item["source"]) for item in items}
        except (KeyError, TypeError) as exc:
            raise UnsupportedConfigurationError(
                f"Feature config for '{feature_name}' must contain "
                "window/source pairs."
            ) from exc
        config[feature_name] = [
            {"window": window, "source": source}
            for window, source in sorted(unique)
        ]

    return config, shift_map
