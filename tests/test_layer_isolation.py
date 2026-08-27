"""Architecture guardrail: enforce the layered dependency direction from ADR 0001.

Directory nesting alone doesn't stop a lower layer from importing a higher one;
this test does. Allowed dependency direction: api -> services -> domain/shared,
with shared as the most foundational (no upward imports at all).
"""

import ast
from pathlib import Path

import pytest

AISERVER_ROOT = Path(__file__).resolve().parents[1] / "src" / "aiserver"

# (layer directory, banned import prefixes for that layer)
LAYER_RULES = {
    "domain": ("aiserver.api", "aiserver.services"),
    "shared": ("aiserver.api", "aiserver.services", "aiserver.domain"),
    "services": ("aiserver.api",),
}


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
