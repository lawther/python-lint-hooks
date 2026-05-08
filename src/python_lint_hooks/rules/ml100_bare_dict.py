"""ML100 — function returns a bare (unparameterised) dict.

`dict` with no type parameters gives callers no information about what the dictionary
contains. Use a dataclass to give the return value a name and typed fields.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, register


def _noqa_lines(returns: ast.expr) -> list[int]:
    start = returns.lineno
    end = returns.end_lineno
    if end is not None and end != start:
        return list(range(start, end + 1))
    return [start]


@register
class ML100(Rule):
    code: ClassVar[str] = "ML100"
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a bare `dict`"
    suggestion: ClassVar[str] = "Use a dataclass instead"

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
                f"Function '{func_name}' returns bare dict; use a dataclass instead",
                noqa_lines=_noqa_lines(returns),
            )
