from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CONTEXTS = ("research", "market_data", "signals", "execution")
FOUNDATION_REPOSITORY_EXCEPTION = (
    BACKEND / "research" / "services" / "_foundation_flow.py",
    "backend.signals.repositories",
)
SERVICE_DATABASE_EXCEPTIONS = tuple(
    (BACKEND / context / "services" / module, "backend.database")
    for context, module in (
        ("market_data", "ingestion_runtime.py"),
        ("market_data", "ops.py"),
        ("market_data", "readiness.py"),
        ("market_data", "tick_governance.py"),
        ("research", "_foundation_flow.py"),
        ("research", "capability_gates.py"),
        ("research", "governance.py"),
        ("research", "micro_kpis.py"),
        ("research", "tradability.py"),
    )
)


@dataclass(frozen=True)
class ImportReference:
    modules: tuple[str, ...]
    line: int


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_name(path: Path) -> str:
    module = _module_name(path)
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _from_import_modules(
    node: ast.ImportFrom,
    *,
    package: str,
) -> tuple[str, ...]:
    if node.level:
        relative_name = "." * node.level + (node.module or "")
        base = importlib.util.resolve_name(relative_name, package)
    else:
        base = node.module or ""
    modules = [base] if base else []
    modules.extend(
        f"{base}.{alias.name}"
        for alias in node.names
        if base and alias.name != "*"
    )
    return tuple(modules)


def _imports(path: Path) -> list[ImportReference]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _package_name(path)
    imported: list[ImportReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(
                ImportReference((alias.name,), node.lineno) for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            imported.append(
                ImportReference(
                    _from_import_modules(node, package=package),
                    node.lineno,
                )
            )
    return imported


def _python_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py")) if path.exists() else []


def _context_layer_files(layer: str) -> list[Path]:
    return [
        path
        for context in CONTEXTS
        for path in _python_files(BACKEND / context / layer)
    ]


def _layer_prefixes(*layers: str) -> tuple[str, ...]:
    return tuple(
        f"backend.{context}.{layer}"
        for context in CONTEXTS
        for layer in layers
    )


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _assert_no_import_prefixes(
    files: list[Path],
    forbidden: tuple[str, ...],
    *,
    exceptions: tuple[tuple[Path, str], ...] = (),
) -> None:
    violations = []
    for path in files:
        for reference in _imports(path):
            matched = next(
                (
                    module
                    for module in reference.modules
                    if any(_matches_prefix(module, prefix) for prefix in forbidden)
                ),
                None,
            )
            if matched is not None:
                if any(
                    path == exception_path
                    and _matches_prefix(matched, exception_prefix)
                    for exception_path, exception_prefix in exceptions
                ):
                    continue
                violations.append(
                    f"{path.relative_to(ROOT)}:{reference.line} -> {matched}"
                )
    assert not violations, "Forbidden backend imports:\n" + "\n".join(violations)


def test_relative_and_package_member_imports_resolve_to_full_modules():
    relative_node = ast.parse(
        "from ...signals.repositories._store import get_adaptive_profile"
    ).body[0]
    package_member_node = ast.parse(
        "from backend.signals import repositories"
    ).body[0]

    assert isinstance(relative_node, ast.ImportFrom)
    assert isinstance(package_member_node, ast.ImportFrom)
    assert "backend.signals.repositories._store" in _from_import_modules(
        relative_node,
        package="backend.research.repositories",
    )
    assert "backend.signals.repositories" in _from_import_modules(
        package_member_node,
        package="backend.research.repositories",
    )


def test_contracts_do_not_depend_on_inner_runtime_layers():
    _assert_no_import_prefixes(
        _context_layer_files("contracts"),
        (
            "backend.database",
            *_layer_prefixes("domain", "repositories", "services", "api"),
            "scripts",
        ),
    )


def test_domain_logic_does_not_depend_on_io_or_orchestration():
    _assert_no_import_prefixes(
        _context_layer_files("domain"),
        (
            "backend.database",
            *_layer_prefixes("repositories", "services", "api"),
            "scripts",
        ),
    )


def test_policies_remain_free_of_io_and_orchestration():
    _assert_no_import_prefixes(
        _context_layer_files("policies"),
        (
            "backend.database",
            *_layer_prefixes("contracts", "repositories", "services", "api"),
            "scripts",
        ),
    )


def test_repositories_do_not_project_domain_or_call_services():
    _assert_no_import_prefixes(
        _context_layer_files("repositories"),
        (
            *_layer_prefixes("api", "domain", "services"),
            "scripts",
        ),
    )


def test_contexts_do_not_import_other_context_repositories():
    violations = []
    exception_path, exception_prefix = FOUNDATION_REPOSITORY_EXCEPTION
    for context in CONTEXTS:
        for path in _python_files(BACKEND / context):
            for reference in _imports(path):
                target = next(
                    (
                        module
                        for module in reference.modules
                        if len(module.split(".")) >= 3
                        and module.split(".")[0] == "backend"
                        and module.split(".")[1] in CONTEXTS
                        and module.split(".")[2] == "repositories"
                        and module.split(".")[1] != context
                    ),
                    None,
                )
                if target is None:
                    continue
                if path == exception_path and _matches_prefix(
                    target, exception_prefix
                ):
                    continue
                violations.append(
                    f"{path.relative_to(ROOT)}:{reference.line} -> {target}"
                )

    assert not violations, "Cross-context repository imports:\n" + "\n".join(
        violations
    )


def test_api_modules_delegate_without_database_or_repository_access():
    _assert_no_import_prefixes(
        [
            BACKEND / context / "api.py"
            for context in CONTEXTS
            if (BACKEND / context / "api.py").exists()
        ],
        (
            "backend.database",
            *_layer_prefixes("domain", "repositories"),
            "scripts",
        ),
    )


def test_services_reject_unapproved_database_api_or_command_imports():
    _assert_no_import_prefixes(
        _context_layer_files("services"),
        (
            "backend.database",
            *_layer_prefixes("api"),
            "scripts",
        ),
        exceptions=SERVICE_DATABASE_EXCEPTIONS,
    )


def test_shared_analytics_remains_database_and_service_free():
    _assert_no_import_prefixes(
        _python_files(BACKEND / "shared" / "analytics"),
        (
            "backend.database",
            *_layer_prefixes("repositories", "services"),
            "scripts",
        ),
    )


def test_backend_never_imports_command_scripts():
    _assert_no_import_prefixes(_python_files(BACKEND), ("scripts",))
