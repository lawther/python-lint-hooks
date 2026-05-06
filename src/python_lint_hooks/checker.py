"""AST-based checks for bare return types and classes defined inside functions."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TypeAlias

_DICT_NAMES: frozenset[str] = frozenset({"dict", "Dict"})
_TUPLE_NAMES: frozenset[str] = frozenset({"tuple", "Tuple"})

_FuncNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef


class _BareKind(Enum):
    """Which bare built-in type was found in a return annotation."""

    NONE = auto()
    DICT = auto()
    TUPLE = auto()


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


def _kind_from_name(name: str) -> _BareKind:
    """Map a bare name string to its BareKind, or NONE if not a bare type."""
    if name in _DICT_NAMES:
        return _BareKind.DICT
    if name in _TUPLE_NAMES:
        return _BareKind.TUPLE
    return _BareKind.NONE


def _find_bare_kind_subscript(node: ast.Subscript) -> _BareKind:
    """Resolve a Subscript annotation node to a BareKind."""
    head = node.value
    if isinstance(head, ast.Name):
        kind = _kind_from_name(head.id)
        if kind is not _BareKind.NONE:
            return kind
        if head.id == "Optional":
            return _find_bare_kind(node.slice)
        if head.id == "Union":
            elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            for elt in elts:
                kind = _find_bare_kind(elt)
                if kind is not _BareKind.NONE:
                    return kind
    elif isinstance(head, ast.Attribute):
        return _kind_from_name(head.attr)
    return _BareKind.NONE


def _find_bare_kind(node: ast.expr) -> _BareKind:
    """Return which bare built-in type the annotation resolves to, or NONE.

    Handles: dict, tuple, Dict, Tuple, typing.Dict, typing.Tuple,
    Optional[dict/tuple], Union[dict/tuple, ...], dict|None, tuple|None,
    and nested combinations thereof.

    Does NOT flag dict/tuple appearing only as type arguments to another
    container — e.g. list[dict[str, str]] returns NONE because the return
    type is a list, not a dict.
    """
    if isinstance(node, ast.Name):
        return _kind_from_name(node.id)
    if isinstance(node, ast.Attribute):
        return _kind_from_name(node.attr)
    if isinstance(node, ast.Subscript):
        return _find_bare_kind_subscript(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _find_bare_kind(node.left)
        return left if left is not _BareKind.NONE else _find_bare_kind(node.right)
    return _BareKind.NONE


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
            return True  # bare
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
            kind = _find_bare_kind(node.returns)
            if kind is not _BareKind.NONE:
                match kind:
                    case _BareKind.DICT:
                        code = "ML001"
                        message = f"Function '{node.name}' returns bare dict; use a dataclass instead"
                    case _BareKind.TUPLE:
                        code = "ML002"
                        message = f"Function '{node.name}' returns bare tuple; use a NamedTuple instead"
                noqa_lines = [node.lineno]
                if node.returns.end_lineno is not None and node.returns.end_lineno != node.lineno:
                    noqa_lines.append(node.returns.end_lineno)
                if not _has_noqa(self._source_lines, noqa_lines, code):
                    self.violations.append(
                        Violation(
                            code=code,
                            message=message,
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
        if self._function_depth > 0 and not _has_noqa(self._source_lines, [node.lineno], "ML003"):
            self.violations.append(
                Violation(
                    code="ML003",
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
