"""ML109 — casting between two NewTypes that wrap the same base.

When code has to write `T(x)` where `x` is already typed `U` and both `T` and
`U` are `NewType`s over the same base (e.g. both wrap `str`), the cast is a
no-op at runtime that only exists to satisfy the type checker. This is the
classic symptom of two parallel NewTypes being introduced for the same concept
in different modules; the usual fix is to unify them.

When the two really are distinct concepts that only coincide in some cases, the
fix is instead to name the conversion once — a function whose signature declares
it (`def f(x: U) -> T: return T(x)`) is exempt, so the rationale lives in one
docstring rather than being re-explained at every call site.
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

    Nor is a designated converter: `def f(x: U) -> T: return T(x)`, where the cast is
    the function's direct return value and its argument is one of that function's own
    parameters. If two NewTypes must stay distinct — because they model genuinely
    different concepts that merely coincide — that function is the way to say so, and
    the rule stays out of its way.
    """

    code: ClassVar[RuleCode] = RuleCode.ML109
    category: ClassVar[RuleCategory] = RuleCategory.TYPE_HYGIENE
    summary: ClassVar[str] = "Cast between two `NewType`s of the same base"
    suggestion: ClassVar[str] = "Unify the two NewTypes, or route the conversion through one named converter function"

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
        """
GoogleEventId = NewType("GoogleEventId", str)
GCalEventId = NewType("GCalEventId", str)

# Legacy events carry no GCal id of their own, so they adopt the Google one.
def adopt_google_event_id(google: GoogleEventId) -> GCalEventId:
    return GCalEventId(google)

def consume(eid: GCalEventId) -> None: ...

def caller(google: GoogleEventId) -> None:
    consume(adopt_google_event_id(google))
""",
    ]
