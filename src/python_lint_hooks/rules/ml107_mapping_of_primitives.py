"""ML107 — function returns a Mapping of primitive types.

`Mapping[str, str]` and similar all-primitive mappings carry no semantic meaning.
Use a dataclass for structured data, or `NewType` to give key/value types meaningful names.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register


@register
class ML107(Rule):
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
