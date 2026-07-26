from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register


@register
class ML104(Rule):
    """Function returns a variable-length tuple.

    Variable-length tuples like `tuple[int, ...]` are immutable, which is often
    desirable, but Python's `list[T]` is more idiomatic for collections of
    homogeneous items. If you need immutability, consider a custom frozen
    collection or a dataclass wrapping a list.
    """

    code: ClassVar[RuleCode] = RuleCode.ML104
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a variable-length `tuple`"
    suggestion: ClassVar[str] = "Use `list[T]` or a custom collection instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._function_depth == 0 and node.returns is not None:
            self._check_return(node.name, node.returns)
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def _check_return(self, func_name: str, returns: ast.expr) -> None:
        analyzer = ForbiddenTypeAnalyzer()
        analyzer.analyze(returns)
        for finding in analyzer.findings:
            if finding.code != self.code:
                continue
            self.report(
                finding.line,
                finding.col,
                f"Function '{func_name}' returns variable-length tuple; use list[T] or custom collection instead",
                noqa_lines=annotation_noqa_lines(returns),
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def get_scores() -> tuple[int, ...]:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
def get_scores() -> list[int]:
    ...
"""
    ]
