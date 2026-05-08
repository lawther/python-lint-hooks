"""ML300 — class defined inside a function.

Classes at function scope are implementation details that cannot be reused or tested
independently. Move them to module level.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, register


@register
class ML300(Rule):
    code: ClassVar[str] = "ML300"
    category: ClassVar[RuleCategory] = RuleCategory.SCOPE
    summary: ClassVar[str] = "Class defined inside a function"
    suggestion: ClassVar[str] = "Move it to module level"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        if self._function_depth > 0:
            self.report(
                node.lineno,
                node.col_offset + 1,
                f"Class '{node.name}' defined inside a function",
            )
