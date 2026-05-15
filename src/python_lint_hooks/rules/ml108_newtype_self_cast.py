"""ML108 — wrapping a NewType around a value already of that type.

`T(x)` where `x` is statically already typed `T` is a runtime no-op that only
serves to satisfy the type checker after a refactor or a copy-paste. The cast
adds noise without changing behaviour or the static type.
"""

from __future__ import annotations

from typing import ClassVar

from python_lint_hooks.analyzers.newtype_casts import CastFinding, CastKind
from python_lint_hooks.rules import RuleCategory, RuleCode, register
from python_lint_hooks.rules._newtype_cast_base import NewTypeCastRuleBase


@register
class ML108(NewTypeCastRuleBase):
    """No-op `NewType` cast: `T(x)` where `x` is statically of type `T`.

    Wrapping a value in its own NewType does nothing at runtime and nothing
    at type-check time — both sides already agree on the type. Remove the
    wrapping call.

    The rule only fires when the argument's static type can be determined
    from local annotations, function parameters, attribute access into a
    known project class, a project function's return annotation, or the
    element type of an iterable in a `for` loop or comprehension. Literal
    arguments (`T("abc")`) and explicit widening (`T(str(x))`) are never
    flagged, and when the argument's type can't be resolved the rule stays
    silent.
    """

    code: ClassVar[RuleCode] = RuleCode.ML108
    category: ClassVar[RuleCategory] = RuleCategory.TYPE_HYGIENE
    summary: ClassVar[str] = "No-op `NewType` cast (value already of that type)"
    suggestion: ClassVar[str] = "Drop the redundant cast"

    def _handle_finding(self, finding: CastFinding) -> None:
        if finding.kind is not CastKind.SELF:
            return
        self.report(
            finding.line,
            finding.col,
            (
                f"No-op NewType cast: '{finding.constructor.name}' wraps a value already of "
                f"that type; drop the wrapping call"
            ),
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
