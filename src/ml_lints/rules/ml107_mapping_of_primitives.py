from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from ml_lints.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register

if TYPE_CHECKING:
    import ast


@register
class ML107(Rule):
    """Function returns a Mapping of primitive types.

    Returning a `Mapping[str, str]` or similar all-primitive mapping is
    semantically "thin". It gives the caller no information about what the
    keys or values represent. This encourages "primitive obsession". Use a
    dataclass for structured data, or `NewType` to give keys/values meaningful names.
    """

    code: ClassVar[RuleCode] = RuleCode.ML107
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a `Mapping` of primitives"
    suggestion: ClassVar[str] = "Use a dataclass or `NewType` for keys/values"

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
                f"Function '{func_name}' returns Mapping of primitives; use NewType for keys/values or use a dataclass",
                noqa_lines=annotation_noqa_lines(returns),
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def get_headers() -> Mapping[str, str]:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
HeaderName = NewType("HeaderName", str)
HeaderValue = NewType("HeaderValue", str)
def get_headers() -> Mapping[HeaderName, HeaderValue]:
    ...
""",
    ]
