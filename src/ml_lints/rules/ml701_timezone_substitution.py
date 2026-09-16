"""ML701 — a timezone is silently substituted instead of a bad one being rejected.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import ClassVar, NamedTuple

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register

# Constructors and constants that produce a tzinfo. A fallback branch evaluating to one
# of these is the whole trigger: it means the code invented a zone rather than refusing
# a value it had just discovered was the wrong kind.
_ZONE_CONSTRUCTORS: frozenset[str] = frozenset({"ZoneInfo", "timezone"})
_ZONE_CONSTANTS: frozenset[str] = frozenset({"UTC", "utc"})

# Only `ZoneInfo` can turn a value into a *real* zone; `timezone(...)` always yields a
# fixed offset. Used to recognise the live alternative a fallback branch displaces.
_IANA_CONSTRUCTORS: frozenset[str] = frozenset({"ZoneInfo"})

# `ZoneInfo(key="UTC")` is the same call as `ZoneInfo("UTC")`, so the zone's identity has
# to be looked for under both spellings.
_ZONE_KEYWORD: str = "key"

# Mapping methods whose trailing argument stands in for a lookup that has already
# failed. A zone there is a substitution, not a default a reader chose up front.
_LOOKUP_METHODS: frozenset[str] = frozenset({"get", "pop", "setdefault"})
_LOOKUP_METHOD_ARGC: int = 2  # d.get(key, default)


class _DefaultingBuiltin(NamedTuple):
    """A builtin whose final positional argument is the value used when lookup fails."""

    name: str
    argc: int


_DEFAULTING_BUILTINS: tuple[_DefaultingBuiltin, ...] = (
    _DefaultingBuiltin("getattr", 3),
    _DefaultingBuiltin("next", 2),
)


class _ScopeKind(Enum):
    """Which of `_function_stack` / `_class_stack` was pushed most recently.

    Function scopes chain for closures regardless of what is interleaved above them, so
    `_function_stack` alone is enough to answer "is this name a closed-over local".  A
    class scope does not chain at all — not even into a class nested inside it — so it
    only answers "is this name bound in the class body I am *directly* inside right now",
    which is exactly what the top of this stack says.
    """

    FUNCTION = auto()
    CLASS = auto()


class _LineSpan(NamedTuple):
    """The inclusive line range of a block of statements."""

    start: int
    end: int

    def contains(self, line: int) -> bool:
        return self.start <= line <= self.end


class _Candidate(NamedTuple):
    """A zone returned from a guarded arm, pending proof that a real zone was reachable."""

    line: int
    col: int
    fallback: str


@dataclass(frozen=True)
class _FunctionFrame:
    """Per-function accumulator for the guarded-arm shape.

    A zone returned from an absence guard or an `except` handler is only a *substitution*
    when the same function can also build a real zone from a value. Both halves are
    discovered as the walker passes them, so the verdict waits until the function closes.

    `reaches_a_real_zone` flips via `dataclasses.replace` rather than assignment, but
    `candidates` and `zone_names` are still mutated in place — replacing the frame carries
    the same list/set objects over, so accumulation into them keeps working unchanged.
    """

    candidates: list[_Candidate] = field(default_factory=list)
    reaches_a_real_zone: bool = False
    zone_names: set[str] = field(default_factory=set)


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_single_identity_test(test: ast.expr, op: type[ast.cmpop]) -> bool:
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], op)
        and _is_none(test.comparators[0])
    )


def _is_absence_test(test: ast.expr) -> bool:
    """True for `x is None` and `not x` — the tests whose body is the fallback arm."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return True
    return _is_single_identity_test(test, ast.Is)


def _is_presence_test(test: ast.expr) -> bool:
    """True for `x is not None` and a bare `x` — the tests whose `else` is the fallback arm."""
    if isinstance(test, (ast.Name, ast.Attribute)):
        return True
    return _is_single_identity_test(test, ast.IsNot)


def _span_of(body: list[ast.stmt]) -> list[_LineSpan]:
    if not body:
        return []
    end = body[-1].end_lineno
    return [_LineSpan(body[0].lineno, end if end is not None else body[-1].lineno)]


def _fallback_arms(node: ast.If) -> list[_LineSpan]:
    """The arm of *node* that runs when the zone is unavailable, if the test says which."""
    if _is_absence_test(node.test):
        return _span_of(node.body)
    if _is_presence_test(node.test):
        return _span_of(node.orelse)
    return []


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_a_constant_zone_identity(node: ast.expr, constant_names: set[str]) -> bool:
    """True when the zone a constructor call names was fixed when the code was written.

    `ZoneInfo("UTC")` and `ZoneInfo(_DEFAULT_ZONE_NAME)` over a module-level
    `_DEFAULT_ZONE_NAME = "UTC"` are the same program, so both count. A name resolved at
    runtime does not: it carries a zone somebody upstream supplied.
    """
    if isinstance(node, ast.Constant):
        return True
    return isinstance(node, ast.Name) and node.id in constant_names


def _zone_identity_argument(node: ast.Call) -> ast.expr | None:
    """The argument naming the zone, written either positionally or as `key=`."""
    if node.args:
        return node.args[0]
    return next((kw.value for kw in node.keywords if kw.arg == _ZONE_KEYWORD), None)


def _builds_zone_from_a_value(node: ast.Call, constant_names: set[str]) -> bool:
    """True for `ZoneInfo(name)` — a real zone derived from something, not a hard-coded one.

    Only `ZoneInfo` qualifies. `timezone(offset)` yields a fixed offset however the offset
    was arrived at, and a fixed offset is never the zone the caller had.
    """
    if _called_name(node) not in _IANA_CONSTRUCTORS:
        return False
    identity = _zone_identity_argument(node)
    if identity is None:
        return False
    return not _is_a_constant_zone_identity(identity, constant_names)


def _lookup_defaults(node: ast.Call) -> list[ast.expr]:
    """The argument of *node* that is used when the lookup it performs finds nothing."""
    name = _called_name(node)
    if isinstance(node.func, ast.Attribute) and name in _LOOKUP_METHODS and len(node.args) == _LOOKUP_METHOD_ARGC:
        return [node.args[-1]]
    if isinstance(node.func, ast.Name):
        for builtin in _DEFAULTING_BUILTINS:
            if name == builtin.name and len(node.args) == builtin.argc:
                return [node.args[-1]]
    return []


def _is_zone_literal(node: ast.expr, constant_names: set[str]) -> bool:
    """True when *node* is an invented timezone: a constructor call or a UTC constant.

    A zone built from a value is excluded. `ZoneInfo(tzinfo)` hands back the very zone its
    caller passed in, so falling back to it is the fix this rule recommends, not the
    defect it describes.
    """
    if isinstance(node, ast.Call):
        if _builds_zone_from_a_value(node, constant_names):
            return False
        return _called_name(node) in _ZONE_CONSTRUCTORS
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

    Indirection does not change the trade. A fallback named ``_FALLBACK`` and a lookup
    default such as ``zones.get(key, timezone.utc)`` invent a zone exactly as the
    one-liner does, and so does the longer form the pattern grows into once it has
    logging attached — an early return under ``if tz_name is None`` or an ``except
    ZoneInfoNotFoundError`` arm that hands back ``ZoneInfo("UTC")``.

    **Two fixes, and which one applies.** Where nobody has the zone, fail fast: raise
    when it is absent or is not a ``ZoneInfo``, so the caller that supplied it is the
    thing that gets fixed. But often the zone is not *bad*, only out of reach — a Google
    Calendar all-day node is ``{"date": "2026-03-18"}`` with no ``timeZone`` because
    Google means the day in the timezone of the *calendar* the event lives on, and that
    zone is sitting in the database the caller is holding open. Then the fix is to thread
    it in as a parameter, not to raise: raising sends the author to the wrong place.
    Reject when the zone does not exist; supply it when something upstream has it.

    A note on runtime guards: an ``isinstance`` check inside a memoised function is not
    load-bearing. Aware datetimes with equal offsets compare and hash equal
    (``datetime(2026, 3, 16, tzinfo=timezone.utc)`` equals the same instant built with
    ``ZoneInfo("UTC")``, and ``ZoneInfo("Australia/Sydney")`` equals a
    ``timedelta(hours=11)`` offset), so an ``lru_cache`` keyed on one cannot tell the two
    apart and a warm cache returns without ever reaching the guard. Put the guard at the
    boundary, ahead of the cache.
    """

    code: ClassVar[RuleCode] = RuleCode.ML701
    category: ClassVar[RuleCategory] = RuleCategory.TIME_CORRECTNESS
    summary: ClassVar[str] = "Timezone silently substituted instead of rejected"
    suggestion: ClassVar[str] = "Take the zone from the caller that has it, or raise if nobody does — never invent one"

    exemptions: ClassVar[str] = (
        "Only a fallback that evaluates to a timezone is flagged — a `ZoneInfo(...)` or `timezone(...)` "
        "call, a `UTC` / `timezone.utc` constant, or a name bound to one of those. Ordinary defaulting "
        "such as `name = row.name or 'unknown'` is not this rule's business.\n\n"
        "A default argument (`def f(tz: ZoneInfo = ZoneInfo('UTC'))`) is not flagged. The zone is chosen "
        "at the signature where a reader can see it, and a caller can override it — unlike a lookup "
        "default such as `zones.get(key, timezone.utc)`, which is swapped in after the lookup has "
        "already reported the real zone missing.\n\n"
        "A guarded arm returning a zone is flagged only when the same function can also build a real "
        "zone from a value. A function that only ever hands back a fixed constant — "
        "`def utc() -> ZoneInfo: return ZoneInfo('UTC')` — has substituted nothing.\n\n"
        "A zone built from a value is not an invented one. `ZoneInfo(tzinfo)` hands back the zone "
        "its caller supplied, so falling back to it — whether inline or through a name it was bound "
        "to — is the fix this rule recommends rather than the defect it describes. A zone whose name "
        "was fixed when the code was written still counts, including through a module-level string "
        "constant: `ZoneInfo(_DEFAULT_ZONE_NAME)` over `_DEFAULT_ZONE_NAME = 'UTC'` is the same "
        "program as `ZoneInfo('UTC')`. Only `ZoneInfo` can derive a zone this way — `timezone(...)` "
        "yields a fixed offset however the offset was arrived at, and a fixed offset is never the "
        "zone the caller had.\n\n"
        "A name is recognised as a zone only when it is bound in the same file, either at module level "
        "or earlier in the same scope. An alias imported from another module is opaque here, and "
        "silence is the honest answer when the rule cannot see the binding. The same limit applies to "
        "the string constants above: only module-level ones are resolved, so an imported name or a "
        "local string leaves the zone looking derived."
    )

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        # Module-level names bound to a timezone, so `x or _FALLBACK` reads like `x or UTC`.
        # Function-local bindings live on the frame instead, and go out of scope with it.
        self._module_zone_names: set[str] = set()
        # Module-level names bound to a string literal, so `ZoneInfo(_DEFAULT_ZONE_NAME)`
        # reads as the invented `ZoneInfo("UTC")` it is.
        self._module_constant_names: set[str] = set()
        # One frame per enclosing function; the innermost owns any guarded-arm finding.
        self._function_stack: list[_FunctionFrame] = []
        # One set per enclosing class body.
        self._class_stack: list[set[str]] = []
        # Push order of the two stacks above, so a binding or lookup can tell which one is
        # the scope it is currently, literally inside — see `_ScopeKind`.
        self._scope_kinds: list[_ScopeKind] = []
        # Line spans of the arms that run when a zone turns out to be unavailable.
        self._arm_stack: list[list[_LineSpan]] = []

    # ------------------------------------------------------------------
    # Zone-valued names
    #
    # A module-level constant may legally be defined below the function that reads it —
    # the name is resolved when the function runs, not when it is defined — so the
    # module's own statements are scanned up front. Everything nested is picked up as
    # the single walk reaches it.
    # ------------------------------------------------------------------

    def enter_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self._note_string_constant(stmt)
        for stmt in node.body:
            self._note_zone_binding(stmt)

    def _note_string_constant(self, stmt: ast.stmt) -> None:
        """Record a module-level `NAME = "..."` so a zone built from it counts as invented."""
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            return
        value = stmt.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return
        targets = [stmt.target] if isinstance(stmt, ast.AnnAssign) else stmt.targets
        for target in targets:
            if isinstance(target, ast.Name):
                self._module_constant_names.add(target.id)

    def enter_Assign(self, node: ast.Assign) -> None:
        self._note_zone_binding(node)

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._note_zone_binding(node)

    def _note_zone_binding(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.AnnAssign):
            targets: list[ast.expr] = [stmt.target]
            value = stmt.value
        elif isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        else:
            return
        if value is None or not _is_zone_literal(value, self._module_constant_names):
            return
        if not self._scope_kinds:
            bound = self._module_zone_names
        elif self._scope_kinds[-1] is _ScopeKind.FUNCTION:
            bound = self._function_stack[-1].zone_names
        else:
            bound = self._class_stack[-1]
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)

    def _is_zone_name(self, name: str) -> bool:
        """True when *name* is bound to a zone in this scope, or in an enclosing function.

        A class scope does not "enclose" in this sense — see `_ScopeKind`.
        """
        if name in self._module_zone_names:
            return True
        if any(name in frame.zone_names for frame in self._function_stack):
            return True
        return bool(self._scope_kinds) and self._scope_kinds[-1] is _ScopeKind.CLASS and name in self._class_stack[-1]

    def _is_zone(self, node: ast.expr | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Name) and self._is_zone_name(node.id):
            return True
        return _is_zone_literal(node, self._module_constant_names)

    # ------------------------------------------------------------------
    # `X if <test> else <zone>` and `X or <zone>` are the same defect written two ways:
    # in both, the right-hand branch invents a zone when the left-hand value is
    # unsatisfactory. The fallback being a zone is the entire trigger.
    # ------------------------------------------------------------------

    def enter_IfExp(self, node: ast.IfExp) -> None:
        if self._is_zone(node.orelse):
            self._report_substitution(node.lineno, node.col_offset, ast.unparse(node.orelse))

    def enter_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or) and self._is_zone(node.values[-1]):
            self._report_substitution(node.lineno, node.col_offset, ast.unparse(node.values[-1]))

    # ------------------------------------------------------------------
    # The same trade spread over statements: an absence guard or an `except` arm that
    # hands back a zone, in a function that could have produced a real one.
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._function_stack.append(_FunctionFrame())
        self._scope_kinds.append(_ScopeKind.FUNCTION)

    def leave_FunctionDef(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        frame = self._function_stack.pop()
        self._scope_kinds.pop()
        if not frame.reaches_a_real_zone:
            return
        for candidate in frame.candidates:
            self._report_substitution(candidate.line, candidate.col, candidate.fallback)

    enter_AsyncFunctionDef = enter_FunctionDef
    leave_AsyncFunctionDef = leave_FunctionDef

    def enter_ClassDef(self, _node: ast.ClassDef) -> None:
        self._class_stack.append(set())
        self._scope_kinds.append(_ScopeKind.CLASS)

    def leave_ClassDef(self, _node: ast.ClassDef) -> None:
        self._class_stack.pop()
        self._scope_kinds.pop()

    def enter_If(self, node: ast.If) -> None:
        self._arm_stack.append(_fallback_arms(node))

    def leave_If(self, _node: ast.If) -> None:
        self._arm_stack.pop()

    def enter_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._arm_stack.append(_span_of(node.body))

    def leave_ExceptHandler(self, _node: ast.ExceptHandler) -> None:
        self._arm_stack.pop()

    def enter_Return(self, node: ast.Return) -> None:
        if node.value is None or not self._function_stack or not self._is_zone(node.value):
            return
        if not any(span.contains(node.lineno) for arms in self._arm_stack for span in arms):
            return
        self._function_stack[-1].candidates.append(
            _Candidate(node.lineno, node.col_offset, ast.unparse(node.value)),
        )

    # ------------------------------------------------------------------
    # A lookup that failed, papered over by its own default argument.
    # ------------------------------------------------------------------

    def enter_Call(self, node: ast.Call) -> None:
        if self._function_stack and _builds_zone_from_a_value(node, self._module_constant_names):
            self._function_stack[-1] = replace(self._function_stack[-1], reaches_a_real_zone=True)
        for default in _lookup_defaults(node):
            if self._is_zone(default):
                self._report_substitution(node.lineno, node.col_offset, ast.unparse(default))

    def _report_substitution(self, line: int, col: int, fallback: str) -> None:
        self.report(
            line,
            col + 1,
            f"Timezone silently substituted with '{fallback}'; take the zone from the caller that has it, "
            f"or raise if nobody does",
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
import zoneinfo
from datetime import date, time


class AllDayNode:
    day: date

    def instant_in(self, calendar_tz: zoneinfo.ZoneInfo) -> datetime:
        \"\"\"The caller holds the zone; the node never guesses one.\"\"\"
        return datetime.combine(self.day, time.min, tzinfo=calendar_tz)
""",
        """
def label_for(name: str | None) -> str:
    return name or "unknown"
""",
    ]
