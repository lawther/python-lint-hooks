"""ML108 — wrapping a NewType around a value already of that type.

`T(x)` where `x` is statically already typed `T` is a runtime no-op that only
serves to satisfy the type checker after a refactor or a copy-paste. The cast
adds noise without changing behaviour or the static type.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.newtype_casts import CastKind, NewTypeCastAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML108(Rule):
    """No-op `NewType` cast: `T(x)` where `x` is statically of type `T`.

    Wrapping a value in its own NewType does nothing at runtime and nothing
    at type-check time — both sides already agree on the type. Remove the
    wrapping call.

    The rule only fires when the argument's static type can be determined
    from local annotations, function parameters, attribute access into a
    known project class, or a project function's return annotation. Literal
    arguments (`T("abc")`) and explicit widening (`T(str(x))`) are never
    flagged, and when the argument's type can't be resolved the rule stays
    silent.
    """

    code: ClassVar[RuleCode] = RuleCode.ML108
    category: ClassVar[RuleCategory] = RuleCategory.TYPE_HYGIENE
    summary: ClassVar[str] = "No-op `NewType` cast (value already of that type)"
    suggestion: ClassVar[str] = "Drop the redundant cast"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._analyzer: NewTypeCastAnalyzer | None = None
        if context.project_index is not None:
            self._analyzer = NewTypeCastAnalyzer(str(context.path.resolve()), context.project_index)

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._analyzer is not None:
            self._analyzer.enter_function(node)

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._analyzer is not None:
            self._analyzer.leave_function(node)

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._analyzer is not None:
            self._analyzer.record_ann_assign(node)

    def enter_Call(self, node: ast.Call) -> None:
        if self._analyzer is None:
            return
        finding = self._analyzer.classify_call(node)
        if finding is None or finding.kind is not CastKind.SELF:
            return
        self.report(
            finding.line,
            finding.col,
            f"No-op NewType cast: '{finding.constructor.name}' wraps a value already of that type",
        )

    bad_example: ClassVar[str] = """
UserId = NewType("UserId", str)

def greet(user: UserId) -> None:
    print(UserId(user))
"""

    good_examples: ClassVar[list[str]] = [
        """
UserId = NewType("UserId", str)

def greet(user: UserId) -> None:
    print(user)
""",
        """
UserId = NewType("UserId", str)

def make_user(raw: str) -> UserId:
    return UserId(raw)
""",
    ]
