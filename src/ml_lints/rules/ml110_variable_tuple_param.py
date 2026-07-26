from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register


@register
class ML110(Rule):
    """Function parameter has a variable-length tuple type annotation.

    `tuple[T, ...]` as a parameter type gives no positional structure and is
    semantically equivalent to an untyped sequence. Use `list[T]` for mutable
    collections, `Sequence[T]` for read-only, or a `NamedTuple` when positional
    structure is meaningful.
    """

    code: ClassVar[RuleCode] = RuleCode.ML110
    category: ClassVar[RuleCategory] = RuleCategory.PARAMETER_TYPES
    summary: ClassVar[str] = "Function parameter has variable-length `tuple` annotation"
    suggestion: ClassVar[str] = "Use `list[T]`, `Sequence[T]`, or a NamedTuple instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self._function_depth == 0:
            self._check_params(node)
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def _check_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        all_args: list[ast.arg] = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        if node.args.vararg is not None:
            all_args.append(node.args.vararg)
        if node.args.kwarg is not None:
            all_args.append(node.args.kwarg)

        for arg in all_args:
            if arg.annotation is None:
                continue
            analyzer = ForbiddenTypeAnalyzer()
            analyzer.analyze(arg.annotation)
            if any(f.code == RuleCode.ML104 for f in analyzer.findings):
                self.report(
                    arg.annotation.lineno,
                    arg.annotation.col_offset + 1,
                    f"Parameter '{arg.arg}' is annotated tuple[T, ...]; use list[T], Sequence[T], or NamedTuple",
                    noqa_lines=annotation_noqa_lines(arg.annotation),
                )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def process(row: tuple[object, ...]) -> None:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
from collections.abc import Sequence

def process(row: Sequence[object]) -> None:
    ...
""",
        """
class Row(NamedTuple):
    id: int
    name: str

def process(row: Row) -> None:
    ...
""",
    ]
