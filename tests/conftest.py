import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

scripts_init = Path(ROOT) / "scripts" / "__init__.py"
existing_scripts = sys.modules.get("scripts")
# Pytest can resolve `tests/scripts` first and shadow the repo `scripts` package.
# Force-load the workspace package so `from scripts import ...` is deterministic.
if existing_scripts is None or str(getattr(existing_scripts, "__file__", "")).endswith(
    "tests/scripts/__init__.py"
):
    scripts_spec = importlib.util.spec_from_file_location(
        "scripts",
        scripts_init,
        submodule_search_locations=[str(scripts_init.parent)],
    )
    assert scripts_spec is not None
    assert scripts_spec.loader is not None
    scripts_module = importlib.util.module_from_spec(scripts_spec)
    sys.modules["scripts"] = scripts_module
    scripts_spec.loader.exec_module(scripts_module)


def _load_script_module(script_name: str, module_name: str):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def load_script():
    return _load_script_module
