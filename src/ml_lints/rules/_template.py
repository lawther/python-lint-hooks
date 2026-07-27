"""MLxxx — one-line description of what this rule catches.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register

if TYPE_CHECKING:
    import ast


@register
class MLxxx(Rule):
    """Rationale for rule MLxxx.

    Explain why this rule exists and what it prevents. This docstring is
    automatically included in generated documentation and CLI help.
    """

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

    def enter_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Only inspect top-level function definitions (not nested functions).
        if self._function_depth == 0:
            pass  # TODO: replace with your check logic; call self.report() on violations
        self._function_depth += 1

    def leave_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._function_depth -= 1

    # Async functions follow the same pattern as sync ones.
    enter_AsyncFunctionDef = enter_FunctionDef
    leave_AsyncFunctionDef = leave_FunctionDef

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    # bad_example: ClassVar[str] = """# TODO: Add a snippet that triggers this rule"""

    # good_examples: ClassVar[list[str]] = [
    #     """# TODO: Add a snippet that shows how to re-write the bad example to NOT trigger this rule""",
    # ]
