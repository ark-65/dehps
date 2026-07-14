from __future__ import annotations

import ast
from pathlib import Path

from dehps.engineering.contracts import CodeFile, CodeGraph, CodeSymbol


class CodeGraphBuilder:
    def __init__(self, repository_root: Path | None = None) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()

    def build(self) -> CodeGraph:
        source_root = self.root / "apps/worker-python/dehps"
        test_root = self.root / "apps/worker-python/tests"
        source_files = tuple(self._code_file(path, "source") for path in self._python_files(source_root))
        test_files = tuple(self._code_file(path, "test") for path in self._python_files(test_root))
        interfaces = tuple(
            sorted(
                {
                    symbol.name
                    for file in source_files
                    for symbol in file.symbols
                    if symbol.kind in {"class", "function"} and not symbol.name.startswith("_")
                }
            )
        )
        return CodeGraph(
            root=self.root.as_posix(),
            source_files=source_files,
            test_files=test_files,
            interfaces=interfaces,
        )

    def _python_files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return [
            path
            for path in sorted(root.rglob("*.py"))
            if "__pycache__" not in path.parts and path.name != "__init__.py"
        ]

    def _code_file(self, path: Path, kind: str) -> CodeFile:
        relative = path.relative_to(self.root).as_posix()
        module = relative.removesuffix(".py").replace("/", ".")
        return CodeFile(
            path=relative,
            module=module,
            kind=kind,
            symbols=self._symbols(path),
        )

    @staticmethod
    def _symbols(path: Path) -> tuple[CodeSymbol, ...]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return ()
        symbols: list[CodeSymbol] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(CodeSymbol(node.name, "class", node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(CodeSymbol(node.name, "function", node.lineno))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        symbols.append(CodeSymbol(target.id, "constant", node.lineno))
        return tuple(symbols)
