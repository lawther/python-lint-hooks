"""ML702 — a datetime is floored to midnight without first being converted into a real zone.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register

_REPLACE: str = "replace"
_ASTIMEZONE: str = "astimezone"

# Presence of `hour` is the whole trigger. Flooring the hour is the point at which the
# expression starts meaning "local midnight"; minute, second and microsecond are
# sub-hour and offset-independent on their own.
_MIDNIGHT_KEYWORD: str = "hour"

# Converting *to a fixed offset* is not a conversion for this rule's purposes — it
# produces precisely the value the rule exists to catch. `.astimezone(UTC)` is the
# shape a test uses to imitate what psycopg hands back.
_FIXED_OFFSET_CONSTANTS: frozenset[str] = frozenset({"UTC", "utc"})
_FIXED_OFFSET_CONSTRUCTOR: str = "timezone"


def _is_fixed_offset(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == _FIXED_OFFSET_CONSTRUCTOR
        return isinstance(func, ast.Attribute) and func.attr == _FIXED_OFFSET_CONSTRUCTOR
    if isinstance(node, ast.Attribute):
        return node.attr in _FIXED_OFFSET_CONSTANTS
    if isinstance(node, ast.Name):
        return node.id in _FIXED_OFFSET_CONSTANTS
    return False


def _is_astimezone_call(node: ast.expr) -> bool:
    """True for `x.astimezone(tz)` where *tz* is not a recognisably fixed offset.

    A bare `.astimezone()` converts to the system zone, which is a real one. An argument
    this rule cannot resolve is assumed to be a real zone — ML700 is what polices whether
    that argument was typed as a `ZoneInfo` in the first place.
    """
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != _ASTIMEZONE:
        return False
    return not any(_is_fixed_offset(arg) for arg in node.args)


def _floors_the_hour(node: ast.Call) -> bool:
    return any(keyword.arg == _MIDNIGHT_KEYWORD for keyword in node.keywords)


@register
class ML702(Rule):
    """Datetime floored to midnight without first being converted into a real zone.

    ``instant.replace(hour=0, minute=0, second=0, microsecond=0)`` does not mean "local
    midnight". It means "midnight at whatever offset this value happens to carry" — and
    the offset a value carries is rarely the one the user lives in. A ``timestamptz`` read
    back by psycopg arrives as a *fixed offset*, so flooring it produces 00:00 in that
    offset, which is 23:00 or 01:00 of a different local day. Wednesday 18:30 UTC is
    already Thursday in Sydney: the result is not a shifted boundary but the wrong day
    outright.

    Converting first is what makes the floor mean what it reads as, because
    ``astimezone`` is what attaches a real ``ZoneInfo``::

        start = instant.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    Flooring to midnight is the one datetime operation that can only ever be calendar
    intent — unlike ``+ timedelta(days=1)``, which is just as often a duration and so
    cannot be judged from its shape. That is why this rule keys on ``hour`` and says
    nothing about arithmetic.
    """

    code: ClassVar[RuleCode] = RuleCode.ML702
    category: ClassVar[RuleCategory] = RuleCategory.TIME_CORRECTNESS
    summary: ClassVar[str] = "Datetime floored to midnight without a zone conversion"
    suggestion: ClassVar[str] = "Call `.astimezone(tz)` with a real `ZoneInfo` before flooring"

    exemptions: ClassVar[str] = (
        "Only a `.replace()` whose keywords include `hour` is flagged. `.replace(tzinfo=...)` is "
        "deliberate offset-stripping and is never flagged; `.replace(minute=0)` floors the hour, which "
        "is sub-day and offset-independent; `.replace(day=...)`, `.replace(month=...)` and "
        "`.replace(year=...)` are the same hazard one scale up but are left alone, because bumping a "
        "year is a common sentinel idiom with nothing to do with local midnight.\n\n"
        "The receiver may be an `.astimezone(...)` call directly, or a local variable assigned from one "
        "earlier in the same function. Reassigning that local to something else clears the exemption.\n\n"
        "`.astimezone(UTC)` and `.astimezone(timezone.utc)` do not count as conversions. They produce a "
        "fixed offset — exactly the value this rule exists to catch — so flooring their result still "
        "fires.\n\n"
        "Deliberately constructing the wrong floor in order to assert that it *is* wrong is a legitimate "
        "`# noqa: ML702`. A test that pins this defect's behaviour is the bad pattern on purpose, which is "
        "not the same as silencing a finding — write the reason next to the suppression."
    )

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        # One scope per enclosing function; each maps a local name to whether it was last
        # assigned from an `.astimezone(...)` call. Module level is the base scope.
        self._scopes: list[dict[str, bool]] = [{}]

    # ------------------------------------------------------------------
    # Scope tracking
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scopes.append({})

    def leave_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scopes.pop()

    enter_AsyncFunctionDef = enter_FunctionDef
    leave_AsyncFunctionDef = leave_FunctionDef

    # ------------------------------------------------------------------
    # Which locals currently hold a zone-converted value
    # ------------------------------------------------------------------

    def enter_Assign(self, node: ast.Assign) -> None:
        converted = _is_astimezone_call(node.value)
        for target in node.targets:
            self._record(target, converted=converted)

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        self._record(node.target, converted=_is_astimezone_call(node.value))

    def enter_For(self, node: ast.For) -> None:
        # A loop variable is whatever the iterable yielded; nothing here proves it was
        # converted, and rebinding must clear any earlier exemption.
        self._record(node.target, converted=False)

    def _record(self, target: ast.expr, *, converted: bool) -> None:
        if isinstance(target, ast.Name):
            self._scopes[-1][target.id] = converted
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._record(element, converted=False)

    def _is_converted_local(self, name: str) -> bool:
        # Innermost first, so a closure can still see a conversion done by its enclosing
        # function. An unknown name is not converted.
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return False

    # ------------------------------------------------------------------
    # The sink
    # ------------------------------------------------------------------

    def enter_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute) or node.func.attr != _REPLACE:
            return
        if not _floors_the_hour(node):
            return

        receiver = node.func.value
        if _is_astimezone_call(receiver):
            return
        if isinstance(receiver, ast.Name) and self._is_converted_local(receiver.id):
            return

        rendered = ast.unparse(receiver)
        self.report(
            node.lineno,
            node.col_offset + 1,
            f"'{rendered}' is floored to midnight without a zone conversion, so this means midnight at "
            f"whatever offset it carries; call .astimezone(tz) with a real ZoneInfo first",
        )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def local_midnight(instant: datetime) -> datetime:
    return instant.replace(hour=0, minute=0, second=0, microsecond=0)
"""

    good_examples: ClassVar[list[str]] = [
        """
import zoneinfo


def local_midnight(instant: datetime, tz: zoneinfo.ZoneInfo) -> datetime:
    return instant.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
""",
        """
import zoneinfo


def local_midnight(instant: datetime, tz: zoneinfo.ZoneInfo) -> datetime:
    local = instant.astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)
""",
        """
def strip_offset(instant: datetime) -> datetime:
    return instant.replace(tzinfo=None)
""",
    ]
