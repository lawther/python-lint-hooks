"""ML700 — a timezone parameter or attribute is not typed as a real IANA zone.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register

# Names that mean "this carries a timezone". Matched exactly, or as a suffix after an
# underscore so that user_tz, owner_timezone and calendar_zone are all covered.
_ZONE_NAMES: frozenset[str] = frozenset({"tz", "tzinfo", "timezone", "zone"})
_ZONE_SUFFIXES: tuple[str, ...] = ("_tz", "_timezone", "_zone")

# The one annotation that is a widening mistake whatever the parameter is called.
_TZINFO_NAMES: frozenset[str] = frozenset({"tzinfo"})

# Annotations that erase the distinction between a real zone and a fixed offset.
_WIDENED_NAMES: frozenset[str] = frozenset({"object", "Any", "tzinfo"})

_ZONEINFO_NAMES: frozenset[str] = frozenset({"ZoneInfo"})

# Bound methods receive these implicitly; they are never the timezone.
_IMPLICIT_ARGS: frozenset[str] = frozenset({"self", "cls"})

# A class that subclasses `datetime` inherits signatures this rule cannot narrow:
# `now`, `fromtimestamp` and `astimezone` all take `tzinfo | None` in the stdlib, and
# tightening an override to `ZoneInfo` would fail the type checker. Frozen-clock test
# fakes are built exactly this way, so the whole class is exempt.
_DATETIME_BASES: frozenset[str] = frozenset({"datetime"})


def _subclasses_datetime(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(base, ast.Name) and base.id in _DATETIME_BASES)
        or (isinstance(base, ast.Attribute) and base.attr in _DATETIME_BASES)
        for base in node.bases
    )


def _referenced_names(annotation: ast.expr) -> set[str]:
    """Every bare or dotted name mentioned anywhere in an annotation expression.

    `zoneinfo.ZoneInfo | None` yields {"zoneinfo", "ZoneInfo", "None"}. Attribute access
    contributes the attribute name so that `datetime.tzinfo` and a bare `tzinfo` import
    are treated identically.
    """
    names: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _is_zone_name(name: str) -> bool:
    return name in _ZONE_NAMES or name.endswith(_ZONE_SUFFIXES)


def _noqa_lines(node: ast.expr) -> list[int]:
    """The full line span of an annotation, so a noqa on any of its lines suppresses."""
    end = node.end_lineno
    if end is None or end == node.lineno:
        return [node.lineno]
    return list(range(node.lineno, end + 1))


@register
class ML700(Rule):
    """Timezone parameter or attribute is not typed as a real IANA zone.

    Adding ``timedelta(days=1)`` to an aware datetime is *wall-clock* arithmetic — it
    lands on the same local time the next day, whatever that day's real length — but
    only when the ``tzinfo`` is a real ``ZoneInfo``. A fixed-offset ``tzinfo``, which is
    what psycopg hands back for a ``timestamptz``, makes the identical expression
    absolute: exactly 24 hours, landing on 23:00 or 01:00 instead of midnight across a
    DST transition. ``.replace(hour=0, ...)`` degrades the same way, from "local
    midnight" to "midnight at whatever offset this value happens to carry".

    A linter cannot see a ``tzinfo``'s runtime type, so the annotation is the only place
    the distinction is visible — and a widened annotation (``object``, ``Any``, bare
    ``tzinfo``, or none at all) is where a fixed offset enters the system. Requiring
    ``ZoneInfo`` at the signature stops it at the point of authorship.

    A ``str`` IANA key such as ``"Australia/Sydney"`` is accepted: a string cannot do
    datetime arithmetic, so it cannot cause this defect, and boundary code legitimately
    carries zones in that form. An annotation this rule cannot resolve — a local alias
    or a ``NewType`` — is also accepted, because silence is the honest answer when the
    name is opaque.
    """

    code: ClassVar[RuleCode] = RuleCode.ML700
    category: ClassVar[RuleCategory] = RuleCategory.TIME_CORRECTNESS
    summary: ClassVar[str] = "Timezone parameter or attribute is not typed as a real IANA zone"
    suggestion: ClassVar[str] = "Annotate it `ZoneInfo` so date arithmetic stays wall-clock"

    exemptions: ClassVar[str] = (
        'A `str` annotation is never flagged — an IANA key such as `"Australia/Sydney"` cannot do '
        "datetime arithmetic, so it cannot cause this defect.\n\n"
        "Any annotation containing `ZoneInfo` is accepted, including unions such as `ZoneInfo | None`.\n\n"
        "An annotation this rule cannot resolve — a local alias or a `NewType` — is accepted. The AST "
        "cannot see through it, and flagging every opaque name would punish exactly the wrap-it-in-a-"
        "real-type habit this project asks for.\n\n"
        "`self`, `cls`, `*args` and `**kwargs` are never flagged.\n\n"
        "Nothing inside a class that subclasses `datetime` is flagged. `now`, `fromtimestamp` and "
        "`astimezone` take `tzinfo | None` in the stdlib, so an override cannot narrow to `ZoneInfo` "
        "without failing the type checker — and frozen-clock test fakes are built exactly this way.\n\n"
        "Return annotations are out of scope. A return has no name to key on, so the check would have to "
        "rest on the annotation alone, and `-> object` has legitimate uses unrelated to timezones."
    )

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        # One entry per enclosing class; True when that class subclasses `datetime`.
        self._class_stack: list[bool] = []

    @property
    def _inside_datetime_subclass(self) -> bool:
        return any(self._class_stack)

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self._inside_datetime_subclass:
            return
        args = node.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            if arg.arg in _IMPLICIT_ARGS:
                continue
            self._check_parameter(arg)

    enter_AsyncFunctionDef = enter_FunctionDef

    def _check_parameter(self, arg: ast.arg) -> None:
        named_as_zone = _is_zone_name(arg.arg)

        if arg.annotation is None:
            if named_as_zone:
                self.report(
                    arg.lineno,
                    arg.col_offset + 1,
                    f"Parameter '{arg.arg}' carries a timezone but is unannotated; annotate it ZoneInfo",
                )
            return

        names = _referenced_names(arg.annotation)
        if names & _ZONEINFO_NAMES:
            return

        widened = names & _WIDENED_NAMES if named_as_zone else names & _TZINFO_NAMES
        if not widened:
            return

        rendered = ast.unparse(arg.annotation)
        self.report(
            arg.annotation.lineno,
            arg.annotation.col_offset + 1,
            f"Parameter '{arg.arg}' is annotated '{rendered}', which admits a fixed-offset tzinfo; "
            f"use ZoneInfo so date arithmetic stays wall-clock",
            noqa_lines=_noqa_lines(arg.annotation),
        )

    # ------------------------------------------------------------------
    # Class attributes — dataclass fields and Pydantic model fields alike
    # ------------------------------------------------------------------

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(_subclasses_datetime(node))

    def leave_ClassDef(self, _node: ast.ClassDef) -> None:
        self._class_stack.pop()

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self._class_stack or self._inside_datetime_subclass:
            return
        if not isinstance(node.target, ast.Name):
            return
        if not _is_zone_name(node.target.id):
            return

        names = _referenced_names(node.annotation)
        if names & _ZONEINFO_NAMES or not names & _WIDENED_NAMES:
            return

        rendered = ast.unparse(node.annotation)
        self.report(
            node.annotation.lineno,
            node.annotation.col_offset + 1,
            f"Attribute '{node.target.id}' is annotated '{rendered}', which admits a fixed-offset tzinfo; "
            f"use ZoneInfo so date arithmetic stays wall-clock",
            noqa_lines=_noqa_lines(node.annotation),
        )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
from datetime import date, time


def local_midnight(d: date, tz: object) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=tz)
"""

    good_examples: ClassVar[list[str]] = [
        """
import zoneinfo
from datetime import date, time


def local_midnight(d: date, tz: zoneinfo.ZoneInfo) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=tz)
""",
        """
import zoneinfo


@dataclass(frozen=True)
class SyncContext:
    user_tz: zoneinfo.ZoneInfo
    calendar_id: str
""",
        """
class CalendarOut(BaseModel):
    timezone: str
    summary: str
""",
    ]
