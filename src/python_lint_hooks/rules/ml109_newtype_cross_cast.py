"""ML109 — casting between two NewTypes that wrap the same base.

When code has to write `T(x)` where `x` is already typed `U` and both `T` and
`U` are `NewType`s over the same base (e.g. both wrap `str`), the cast is a
no-op at runtime that only exists to satisfy the type checker. This is the
classic symptom of two parallel NewTypes being introduced for the same concept
in different modules; the fix is to unify them.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.newtype_casts import CastKind, NewTypeCastAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML109(Rule):
    """Cross-`NewType` cast: `T(x)` where `x` is `U`, and `T` and `U` share a base.

    Both NewTypes are runtime-equal to their base, so the cast does nothing at
    runtime; it only papers over a type-checker complaint. If you find yourself
    writing it, the two NewTypes almost certainly model the same underlying
    concept and should be unified into one.

    Fires only when both sides resolve to known project NewTypes with the same
    canonical base. Literals, explicit widening (`T(str(x))`), and
    unresolvable argument types are never flagged.
    """

    code: ClassVar[RuleCode] = RuleCode.ML109
    category: ClassVar[RuleCategory] = RuleCategory.TYPE_HYGIENE
    summary: ClassVar[str] = "Cast between two `NewType`s of the same base"
    suggestion: ClassVar[str] = "Unify the two NewTypes — they model the same concept"

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
        if finding is None or finding.kind is not CastKind.CROSS_SAME_BASE:
            return
        self.report(
            finding.line,
            finding.col,
            (
                f"Cast between NewTypes '{finding.arg_newtype.name}' and "
                f"'{finding.constructor.name}' sharing the same base; unify them"
            ),
        )

    bad_example: ClassVar[str] = """
GoogleEventId = NewType("GoogleEventId", str)
GCalEventId = NewType("GCalEventId", str)

def consume(eid: GCalEventId) -> None: ...

def caller(google: GoogleEventId) -> None:
    consume(GCalEventId(google))
"""

    good_examples: ClassVar[list[str]] = [
        """
EventId = NewType("EventId", str)

def consume(eid: EventId) -> None: ...

def caller(event: EventId) -> None:
    consume(event)
""",
    ]
