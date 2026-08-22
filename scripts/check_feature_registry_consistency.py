"""Verify that the backend feature catalog and frontend fallback are identical."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backend.shared.analytics.features import (
    FEATURE_REGISTRY_VERSION,
    list_feature_definitions,
)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"
FEATURE_FIELDS = (
    "name",
    "label",
    "description",
    "default_window",
    "window_editable",
    "allowed_sources",
    "family",
    "parameter_tuple",
    "required_columns",
)


def _normalized_registry(version: str, features: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_features = [
        {field: feature.get(field) for field in FEATURE_FIELDS}
        for feature in features
    ]
    normalized_features.sort(key=lambda feature: str(feature["name"]))
    return {"version": version, "features": normalized_features}


def _load_frontend_registry() -> dict[str, Any]:
    result = subprocess.run(
        ["bun", "tests/featureRegistry.contract.ts"],
        cwd=FRONTEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "frontend feature registry contract failed:\n"
            f"{result.stdout}{result.stderr}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "frontend feature registry contract did not emit valid JSON:\n"
            f"{result.stdout}{result.stderr}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("frontend feature registry contract returned a non-object")
    return payload


def main() -> int:
    backend_registry = _normalized_registry(
        FEATURE_REGISTRY_VERSION,
        list_feature_definitions(),
    )
    frontend_payload = _load_frontend_registry()
    frontend_features = frontend_payload.get("features")
    if not isinstance(frontend_features, list) or not all(
        isinstance(feature, dict) for feature in frontend_features
    ):
        raise RuntimeError("frontend feature registry contract returned invalid features")
    frontend_registry = _normalized_registry(
        str(frontend_payload.get("version")),
        frontend_features,
    )

    if backend_registry != frontend_registry:
        print("Feature registry consistency check failed.")
        print("Backend:")
        print(json.dumps(backend_registry, indent=2, sort_keys=True))
        print("Frontend fallback:")
        print(json.dumps(frontend_registry, indent=2, sort_keys=True))
        return 1

    print(
        "Feature registry consistency check passed "
        f"({FEATURE_REGISTRY_VERSION}, {len(backend_registry['features'])} features)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
