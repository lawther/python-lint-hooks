"""ML701 — a timezone is silently substituted instead of a bad one being rejected.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import Rule, RuleCategory, RuleCode, register

# Constructors and constants that produce a tzinfo. A fallback branch evaluating to one
# of these is the whole trigger: it means the code invented a zone rather than refusing
# a value it had just discovered was the wrong kind.
_ZONE_CONSTRUCTORS: frozenset[str] = frozenset({"ZoneInfo", "timezone"})
_ZONE_CONSTANTS: frozenset[str] = frozenset({"UTC", "utc"})


def _is_zone_expr(node: ast.expr) -> bool:
    """True when *node* evaluates to a timezone: a ZoneInfo/timezone call, or a UTC constant."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in _ZONE_CONSTRUCTORS
        if isinstance(func, ast.Attribute):
            return func.attr in _ZONE_CONSTRUCTORS
        return False
    if isinstance(node, ast.Attribute):
        return node.attr in _ZONE_CONSTANTS
    if isinstance(node, ast.Name):
        return node.id in _ZONE_CONSTANTS
    return False


@register
class ML701(Rule):
    """A timezone is silently substituted instead of a bad one being rejected.

    ``tz = x if isinstance(x, ZoneInfo) else ZoneInfo("UTC")`` reads as a safety check
    and is the opposite of one. The ``isinstance`` has correctly discovered that ``x`` is
    not a real IANA zone — that it is a fixed offset, most likely a ``timestamptz`` handed
    back by psycopg — and the ``else`` branch then throws that discovery away and carries
    on with an invented zone. Every calendar computation downstream is now silently in the
    wrong zone: not off by an hour, but potentially on the wrong day, because Wednesday
    18:30 UTC is Thursday in Sydney.

    ``tz = user_tz or UTC`` and ``tz = tz if tz else timezone.utc`` are the same trade in
    fewer characters. The substituted zone is a guess, and a guess that is wrong produces
    output that looks entirely plausible, which is what makes the failure expensive to
    find.

    An *absent* zone counts, not only a wrong-kind one, and the fallback being a real
    IANA zone does not make it safe. ``ZoneInfo(payload.time_zone) if payload.time_zone
    else ZoneInfo("UTC")`` still guesses, and for an all-day event floored with
    ``datetime.combine(d, time.min, tzinfo=tz)`` a wrong guess moves the event to the
    wrong *day*, not merely the wrong hour.

    Fail fast and explicitly instead: raise when the zone is absent or is not a
    ``ZoneInfo``, so the caller that supplied it is the thing that gets fixed.
    """

    code: ClassVar[RuleCode] = RuleCode.ML701
    category: ClassVar[RuleCategory] = RuleCategory.TIME_CORRECTNESS
    summary: ClassVar[str] = "Timezone silently substituted instead of rejected"
    suggestion: ClassVar[str] = "Raise when the zone is missing or not a `ZoneInfo` rather than inventing one"

    exemptions: ClassVar[str] = (
        "Only a fallback that evaluates to a timezone is flagged — a `ZoneInfo(...)` or `timezone(...)` "
        "call, or a `UTC` / `timezone.utc` constant. Ordinary defaulting such as "
        "`name = row.name or 'unknown'` is not this rule's business.\n\n"
        "A default argument (`def f(tz: ZoneInfo = ZoneInfo('UTC'))`) is not flagged. The zone is chosen "
        "at the signature where a reader can see it, not swapped in after a check has already failed."
    )

    # ------------------------------------------------------------------
    # `X if <test> else <zone>` and `X or <zone>` are the same defect written two ways:
    # in both, the right-hand branch invents a zone when the left-hand value is
    # unsatisfactory. The fallback being a zone is the entire trigger.
    # ------------------------------------------------------------------

    def enter_IfExp(self, node: ast.IfExp) -> None:
        if _is_zone_expr(node.orelse):
            self._report_substitution(node, ast.unparse(node.orelse))

    def enter_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or) and _is_zone_expr(node.values[-1]):
            self._report_substitution(node, ast.unparse(node.values[-1]))

    def _report_substitution(self, node: ast.expr, fallback: str) -> None:
        self.report(
            node.lineno,
            node.col_offset + 1,
            f"Timezone silently substituted with '{fallback}' instead of rejecting the bad value; "
            f"raise instead so the caller that supplied it gets fixed",
        )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
import zoneinfo


def zone_of(instant: datetime) -> zoneinfo.ZoneInfo:
    tz = instant.tzinfo
    return tz if isinstance(tz, zoneinfo.ZoneInfo) else zoneinfo.ZoneInfo("UTC")
"""

    good_examples: ClassVar[list[str]] = [
        """
import zoneinfo


def zone_of(instant: datetime) -> zoneinfo.ZoneInfo:
    tz = instant.tzinfo
    if not isinstance(tz, zoneinfo.ZoneInfo):
        msg = f"expected a real IANA zone, got {tz!r}"
        raise TypeError(msg)
    return tz
""",
        """
def label_for(name: str | None) -> str:
    return name or "unknown"
""",
    ]
