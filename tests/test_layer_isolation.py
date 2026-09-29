"""Architecture guardrail: enforce the layered dependency direction from ADR 0001.

Directory nesting alone doesn't stop a lower layer from importing a higher one;
this test does. Allowed dependency direction: api -> application -> domain/config.
Infrastructure implements application ports and bootstrap is the only composition root.
"""

import ast
from pathlib import Path

import pytest

AISERVER_ROOT = Path(__file__).resolve().parents[1] / "src" / "aiserver"

# (layer directory, banned import prefixes for that layer)
LAYER_RULES = {
    "config": (
        "aiserver.api",
        "aiserver.application",
        "aiserver.bootstrap",
        "aiserver.contracts",
        "aiserver.infrastructure",
    ),
    "contracts": (
        "aiserver.api",
        "aiserver.application",
        "aiserver.bootstrap",
        "aiserver.infrastructure",
    ),
    "application": ("aiserver.api", "aiserver.bootstrap", "aiserver.infrastructure"),
    "infrastructure": ("aiserver.api", "aiserver.bootstrap"),
}

APPLICATION_FRAMEWORK_IMPORTS = (
    "fastapi",
    "mlflow.genai.agent_server",
    "starlette",
)


def _imported_modules(path: Path) -> set[str]:
    """Collect all `aiserver.*` module names imported by a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _module_path(module: str) -> Path | None:
    if not module.startswith("aiserver."):
        return None
    relative = Path(*module.split(".")[1:])
    module_file = AISERVER_ROOT / relative.with_suffix(".py")
    if module_file.exists():
        return module_file
    package_file = AISERVER_ROOT / relative / "__init__.py"
    return package_file if package_file.exists() else None


def _internal_import_closure(start_paths: list[Path]) -> set[Path]:
    pending = list(start_paths)
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        for module in _imported_modules(path):
            imported_path = _module_path(module)
            if imported_path is not None and imported_path not in visited:
                pending.append(imported_path)
    return visited


def _layer_files():
    for layer, banned_prefixes in LAYER_RULES.items():
        layer_dir = AISERVER_ROOT / layer
        for path in sorted(layer_dir.rglob("*.py")):
            yield layer, banned_prefixes, path


@pytest.mark.parametrize(
    "layer,banned_prefixes,path",
    list(_layer_files()),
    ids=lambda v: str(v) if isinstance(v, Path) else None,
)
def test_layer_does_not_import_higher_layer(layer, banned_prefixes, path):
    modules = _imported_modules(path)
    violations = [
        module
        for module in modules
        if any(module == prefix or module.startswith(prefix + ".") for prefix in banned_prefixes)
    ]
    assert not violations, (
        f"{path.relative_to(AISERVER_ROOT.parent.parent)} (layer={layer}) imports from a "
        f"higher layer, violating ADR 0001's dependency direction: {violations}"
    )


def test_execution_boundary_does_not_import_delivery_frameworks():
    execution_paths = [
        AISERVER_ROOT / "application" / "ports" / "execution.py",
        AISERVER_ROOT / "contracts" / "execution.py",
    ]
    execution_package = AISERVER_ROOT / "application" / "execution"
    if execution_package.exists():
        execution_paths.extend(sorted(execution_package.rglob("*.py")))

    execution_paths = sorted(_internal_import_closure(execution_paths))
    violations = {
        str(path.relative_to(AISERVER_ROOT.parent.parent)): sorted(
            module
            for module in _imported_modules(path)
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in APPLICATION_FRAMEWORK_IMPORTS
            )
        )
        for path in execution_paths
    }
    violations = {path: modules for path, modules in violations.items() if modules}

    assert not violations, (
        "Framework-neutral execution contracts imported delivery frameworks: "
        f"{violations}"
    )
