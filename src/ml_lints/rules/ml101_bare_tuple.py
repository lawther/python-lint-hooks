from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from ml_lints.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register

if TYPE_CHECKING:
    import ast


@register
class ML101(Rule):
    """Function returns a bare (unparameterised) tuple.

    A `tuple` with no type parameters gives callers no information about what the
    tuple contains or its expected length. This makes the code harder to reason
    about and prevents type checkers from verifying how the return value is used.
    Use a `NamedTuple` to provide a named type with explicitly typed fields.
    """

    code: ClassVar[RuleCode] = RuleCode.ML101
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a bare `tuple`"
    suggestion: ClassVar[str] = "Use a NamedTuple instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._function_depth == 0 and node.returns is not None:
            self._check_return(node.name, node.returns)
        self._function_depth += 1

    def leave_FunctionDef(self, _node: ast.FunctionDef) -> None:
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
                f"Function '{func_name}' returns bare tuple; use a NamedTuple instead",
                noqa_lines=annotation_noqa_lines(returns),
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def get_point() -> tuple:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
class Point(NamedTuple):
    x: int
    y: int

def get_point() -> Point:
    ...
""",
    ]
