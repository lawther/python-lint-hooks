"""AST-based checks for bare return types and classes defined inside functions."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

_BARE_NAMES: frozenset[str] = frozenset({"dict", "Dict", "tuple", "Tuple"})

_FuncNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class Violation:
    """A single rule violation found in a source file."""

    code: str
    message: str
    path: Path
    line: int
    col: int

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"


def _is_bare_type(node: ast.expr) -> bool:
    """Return True if the annotation is (or unwraps to) a bare dict or tuple.

    Handles: dict, tuple, Dict, Tuple, typing.Dict, typing.Tuple,
    Optional[dict], Union[dict, ...], dict | None, and nested combinations.
    Does NOT flag dict/tuple when they appear only as type arguments to another
    container (e.g. list[dict[str, str]] is fine — the return type is a list).
    """
    if isinstance(node, ast.Name):
        return node.id in _BARE_NAMES

    if isinstance(node, ast.Attribute):
        return node.attr in _BARE_NAMES

    if isinstance(node, ast.Subscript):
        head = node.value
        if isinstance(head, ast.Name):
            if head.id in _BARE_NAMES:
                return True
            if head.id == "Optional":
                return _is_bare_type(node.slice)
            if head.id == "Union":
                s = node.slice
                if isinstance(s, ast.Tuple):
                    return any(_is_bare_type(e) for e in s.elts)
                return _is_bare_type(s)
        if isinstance(head, ast.Attribute) and head.attr in _BARE_NAMES:
            return True

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_bare_type(node.left) or _is_bare_type(node.right)

    return False


def _has_noqa(source_lines: list[str], line_numbers: list[int], code: str) -> bool:
    """Return True if any of the given source lines carries a noqa suppressing code."""
    for lineno in line_numbers:
        if lineno < 1 or lineno > len(source_lines):
            continue
        line = source_lines[lineno - 1]
        if "# noqa" not in line:
            continue
        _, _, noqa_tail = line.partition("# noqa")
        noqa_tail = noqa_tail.strip()
        if not noqa_tail or not noqa_tail.startswith(":"):
            return True  # bare # noqa suppresses everything
        codes = [c.strip() for c in noqa_tail[1:].split(",")]
        if code in codes:
            return True
    return False


class _Checker(ast.NodeVisitor):
    def __init__(self, path: Path, source_lines: list[str]) -> None:
        self._path = path
        self._source_lines = source_lines
        self._function_depth = 0
        self.violations: list[Violation] = []

    def _visit_function(self, node: _FuncNode) -> None:
        if self._function_depth == 0 and node.returns is not None:
            if _is_bare_type(node.returns):
                # Accept # noqa on either the `def` line or the annotation's last line.
                noqa_lines = [node.lineno]
                if node.returns.end_lineno is not None and node.returns.end_lineno != node.lineno:
                    noqa_lines.append(node.returns.end_lineno)
                if not _has_noqa(self._source_lines, noqa_lines, "ML001"):
                    self.violations.append(
                        Violation(
                            code="ML001",
                            message=(
                                f"Function '{node.name}' returns bare dict or tuple; "
                                "use a NamedTuple or dataclass instead"
                            ),
                            path=self._path,
                            line=node.lineno,
                            col=node.col_offset + 1,
                        )
                    )
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._function_depth > 0:
            if not _has_noqa(self._source_lines, [node.lineno], "ML002"):
                self.violations.append(
                    Violation(
                        code="ML002",
                        message=f"Class '{node.name}' defined inside a function",
                        path=self._path,
                        line=node.lineno,
                        col=node.col_offset + 1,
                    )
                )
        self.generic_visit(node)


def check_file(path: Path) -> list[Violation]:
    """Parse path and return all ML rule violations found."""
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    checker = _Checker(path, source_lines)
    checker.visit(tree)
    return checker.violations
