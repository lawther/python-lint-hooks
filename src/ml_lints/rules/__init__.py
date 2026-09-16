"""Rule base class, registry, and auto-discovery.

Rules are discovered automatically: any module in this package whose name does NOT start
with an underscore is imported at load time, which causes any `@register`-decorated class
inside it to be added to the registry.
"""

from __future__ import annotations

import importlib
import pkgutil
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, TypeVar

from ml_lints.noqa import has_file_noqa, has_noqa
from ml_lints.violation import RuleCode, Violation

if TYPE_CHECKING:
    import ast
    from collections.abc import Sequence
    from pathlib import Path

    from ml_lints.analyzers.newtype_index import NewTypeIndex
    from ml_lints.comments import Comment


class RuleCategory(Enum):
    RETURN_TYPES = "return-types"
    PARAMETER_TYPES = "parameter-types"
    CLASS_SHAPE = "class-shape"
    SCOPE = "scope"
    DATA_TRUST = "data-trust"
    LOCALISATION = "localisation"
    TYPE_HYGIENE = "type-hygiene"
    TESTING = "testing"
    TIME_CORRECTNESS = "time-correctness"
    FILE_INTEGRITY = "file-integrity"


class CheckContext:
    """Immutable per-file context passed to every rule.

    project_index is the optional cross-file NewType / annotation index built by the
    project-wide pre-pass. Rules that need cross-module type resolution (ML108, ML109)
    consume it; single-file rules ignore it.

    encoding is the codec `tokenize.open()` actually used to decode the file (e.g.
    "utf-8", "utf-8-sig" for a BOM, or a PEP 263 declaration like "iso-8859-1"). ML001
    consumes it; other rules ignore it.

    comments holds the file's real comment tokens, as found by `ml_lints.comments`. A rule
    that needs comments must read them from here: searching source_lines for "#" finds
    string literals too. noqa suppression reads them as well, which is why there is no
    default: a context built without them would silently honour no noqa at all.
    """

    __slots__ = ("comments", "encoding", "path", "project_index", "source_lines")

    def __init__(
        self,
        path: Path,
        source_lines: Sequence[str],
        comments: Sequence[Comment],
        project_index: NewTypeIndex | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.path = path
        self.source_lines = source_lines
        self.project_index = project_index
        self.encoding = encoding
        self.comments = comments


class Rule:
    """Base class for all lint rules.

    Rules use enter_<NodeType> / leave_<NodeType> hooks instead of ast.NodeVisitor
    visit_* methods. The runner walks the AST once and dispatches to all rules —
    do NOT recurse inside hook methods.

    Call `self.report(line, col, message)` to emit a violation. noqa handling is
    automatic; pass `noqa_lines` when a noqa on some other line (e.g. elsewhere in a
    multi-line annotation) should also suppress it. Never call `has_noqa` directly.
    """

    code: ClassVar[RuleCode]
    category: ClassVar[RuleCategory]
    summary: ClassVar[str]
    suggestion: ClassVar[str]
    bad_example: ClassVar[str]
    good_examples: ClassVar[list[str]]
    exemptions: ClassVar[str]  # optional prose; rendered as "## Automatic Exemptions" in docs

    # Whole-file rules whose trigger depends on the file's first lines (e.g. ML001,
    # which reads a PEP 263 encoding declaration) can't be tested with the shared
    # PRELUDE, since that always comes first. Set False to test bad_example /
    # good_examples standalone instead. See test_rule_examples.py.
    uses_prelude: ClassVar[bool] = True

    def __init__(self, context: CheckContext) -> None:
        self._context = context
        self.violations: list[Violation] = []

    def report(
        self,
        line: int,
        col: int,
        message: str,
        *,
        noqa_lines: list[int] | None = None,
    ) -> bool:
        """Emit a violation unless noqa suppresses it; return True if it was emitted."""
        lines_to_check = noqa_lines if noqa_lines is not None else [line]
        comments = self._context.comments
        if has_noqa(comments, lines_to_check, self.code) or has_file_noqa(comments, self.code):
            return False
        self.violations.append(
            Violation(
                code=self.code,
                message=message,
                path=self._context.path,
                line=line,
                col=col,
            ),
        )
        return True


def annotation_noqa_lines(returns: ast.expr) -> list[int]:
    """Return the line range of a return annotation for noqa suppression."""
    start = returns.lineno
    end = returns.end_lineno
    if end is not None and end != start:
        return list(range(start, end + 1))
    return [start]


_REGISTRY: list[type[Rule]] = []

_RuleT = TypeVar("_RuleT", bound=Rule)


def register(cls: type[_RuleT]) -> type[_RuleT]:
    """Register a Rule subclass so the runner can discover it."""
    _REGISTRY.append(cls)
    return cls


def all_rules() -> list[type[Rule]]:
    """Return all registered rule classes."""
    return list(_REGISTRY)


def _load_all_rule_modules() -> None:
    """Import every non-underscore module in this package to trigger @register calls."""
    for module_info in pkgutil.iter_modules(__path__):
        if not module_info.name.startswith("_"):
            importlib.import_module(f"{__name__}.{module_info.name}")


_load_all_rule_modules()
