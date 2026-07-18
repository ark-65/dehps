from __future__ import annotations

import ast
from pathlib import Path

from dehps.scoring_kernel import KernelPlanner
import dehps.scoring_kernel as scoring_kernel


WORKER_ROOT = Path(__file__).resolve().parents[1]
EXPLICIT_ORACLE_PATHS = {
    WORKER_ROOT / "scripts" / "benchmark_scoring_kernel.py",
}
FORBIDDEN_RUNTIME_NAMES = {
    "NumpyReferenceBackend",
    "NumbaCpuBackend",
    "_score_matrix",
    "execute_shadow_pair",
    "run_shadow_comparison",
}
RAW_BACKEND_MODULES = {
    "dehps.scoring_kernel.numpy_backend",
    "dehps.scoring_kernel.numba_backend",
}
ALLOWED_IMPLEMENTATION_IMPORTS = {
    Path("dehps/feature_runtime/compiler.py"): {"component_tile"},
    Path("dehps/optimization/walk_forward.py"): {"_ordered_topk"},
}


def _consumer_paths() -> list[Path]:
    return sorted(
        path
        for root in (WORKER_ROOT / "dehps", WORKER_ROOT / "scripts")
        for path in root.rglob("*.py")
        if path not in EXPLICIT_ORACLE_PATHS
        and "scoring_kernel" not in path.relative_to(WORKER_ROOT).parts
    )


def test_application_paths_cannot_reenter_raw_scoring_runtime() -> None:
    violations: list[str] = []
    for path in _consumer_paths():
        relative = path.relative_to(WORKER_ROOT)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in RAW_BACKEND_MODULES:
                    allowed = ALLOWED_IMPLEMENTATION_IMPORTS.get(relative, set())
                    for alias in node.names:
                        if alias.name not in allowed:
                            violations.append(
                                f"{relative}:{node.lineno}:raw-import:{alias.name}"
                            )
                for alias in node.names:
                    if alias.name in FORBIDDEN_RUNTIME_NAMES:
                        violations.append(
                            f"{relative}:{node.lineno}:{alias.name}"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in RAW_BACKEND_MODULES:
                        violations.append(
                            f"{relative}:{node.lineno}:raw-module:{alias.name}"
                        )
                    if alias.asname in FORBIDDEN_RUNTIME_NAMES:
                        violations.append(
                            f"{relative}:{node.lineno}:{alias.asname}"
                        )
            elif isinstance(node, ast.FunctionDef) and node.name in FORBIDDEN_RUNTIME_NAMES:
                violations.append(f"{relative}:{node.lineno}:definition:{node.name}")
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_RUNTIME_NAMES:
                violations.append(f"{relative}:{node.lineno}:name:{node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_RUNTIME_NAMES:
                violations.append(f"{relative}:{node.lineno}:attribute:{node.attr}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "backend"
            ):
                violations.append(f"{relative}:{node.lineno}:backend()")
    assert violations == []


def test_public_kernel_surface_exposes_only_verified_runtime_execution() -> None:
    assert not hasattr(KernelPlanner, "backend")
    assert not hasattr(scoring_kernel, "execute_shadow_pair")
    assert not hasattr(scoring_kernel, "run_shadow_comparison")
