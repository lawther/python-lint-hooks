"""MLxxx — one-line description of what this rule catches.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class MLxxx(Rule):
    code: ClassVar[RuleCode] = RuleCode.MLxxx  # ty: ignore[unresolved-attribute]  # placeholder replaced by just new-rule
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES  # change as appropriate
    summary: ClassVar[str] = "Short description for the README rules table"
    suggestion: ClassVar[str] = "What the author should do instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        # Add rule-local state here (e.g. function depth counter).
        self._function_depth: int = 0

    # ------------------------------------------------------------------
    # enter_* hooks are called when the walker ENTERS a node.
    # leave_* hooks are called when the walker LEAVES a node.
    # Do NOT recurse inside these methods — the runner handles traversal.
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Only inspect top-level function definitions (not nested functions).
        if self._function_depth == 0:
            pass  # TODO: replace with your check logic; call self.report() on violations
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._function_depth -= 1

    # Async functions follow the same pattern as sync ones.
    enter_AsyncFunctionDef = enter_FunctionDef
    leave_AsyncFunctionDef = leave_FunctionDef
