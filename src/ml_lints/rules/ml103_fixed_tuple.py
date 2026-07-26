from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register


@register
class ML103(Rule):
    """Function returns a fixed-length tuple.

    Returning fixed-length tuples like `tuple[int, int]` is often used for simple
    pairs or triples, but it lacks semantic meaning. Callers must remember whether
    `result[0]` is the width or the height, which leads to bugs. Using a `NamedTuple`
    gives each field a meaningful name and makes the API self-documenting.
    """

    code: ClassVar[RuleCode] = RuleCode.ML103
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a fixed-length `tuple`"
    suggestion: ClassVar[str] = "Use a NamedTuple instead"

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
                f"Function '{func_name}' returns fixed-length tuple; use a NamedTuple instead",
                noqa_lines=annotation_noqa_lines(returns),
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def get_dimensions() -> tuple[int, int]:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
class Dimensions(NamedTuple):
    width: int
    height: int

def get_dimensions() -> Dimensions:
    ...
"""
    ]
