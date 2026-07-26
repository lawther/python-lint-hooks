"""ML109 — casting between two NewTypes that wrap the same base.

When code has to write `T(x)` where `x` is already typed `U` and both `T` and
`U` are `NewType`s over the same base (e.g. both wrap `str`), the cast is a
no-op at runtime that only exists to satisfy the type checker. This is the
classic symptom of two parallel NewTypes being introduced for the same concept
in different modules; the fix is to unify them.
"""

from __future__ import annotations

from typing import ClassVar

from ml_lints.analyzers.newtype_casts import CastFinding, CastKind
from ml_lints.rules import RuleCategory, RuleCode, register
from ml_lints.rules._newtype_cast_base import NewTypeCastRuleBase


@register
class ML109(NewTypeCastRuleBase):
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

    def _handle_finding(self, finding: CastFinding) -> None:
        if finding.kind is not CastKind.CROSS_SAME_BASE:
            return
        self.report(
            finding.line,
            finding.col,
            (
                f"Cast between NewTypes '{finding.arg_newtype.name}' and "
                f"'{finding.constructor.name}' over the same base; consider unifying them "
                f"into a single NewType"
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
