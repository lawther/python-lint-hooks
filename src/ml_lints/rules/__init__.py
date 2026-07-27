"""Rule base class, registry, and auto-discovery.

Rules are discovered automatically: any module in this package whose name does NOT start
with an underscore is imported at load time, which causes any `@register`-decorated class
inside it to be added to the registry.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, TypeVar

from ml_lints.noqa import has_noqa
from ml_lints.violation import RuleCode, Violation

if TYPE_CHECKING:
    from pathlib import Path

    from ml_lints.analyzers.newtype_index import NewTypeIndex


class RuleCategory(Enum):
    RETURN_TYPES = "return-types"
    PARAMETER_TYPES = "parameter-types"
    CLASS_SHAPE = "class-shape"
    SCOPE = "scope"
    DATA_TRUST = "data-trust"
    LOCALISATION = "localisation"
    TYPE_HYGIENE = "type-hygiene"
    TESTING = "testing"


class CheckContext:
    """Immutable per-file context passed to every rule.

    project_index is the optional cross-file NewType / annotation index built by the
    project-wide pre-pass. Rules that need cross-module type resolution (ML108, ML109)
    consume it; single-file rules ignore it.
    """

    __slots__ = ("path", "project_index", "source_lines")

    def __init__(
        self,
        path: Path,
        source_lines: tuple[str, ...],
        project_index: NewTypeIndex | None = None,
    ) -> None:
        self.path = path
        self.source_lines = source_lines
        self.project_index = project_index


class Rule:
    """Base class for all lint rules.

    Rules use enter_<NodeType> / leave_<NodeType> hooks instead of ast.NodeVisitor
    visit_* methods. The runner walks the AST once and dispatches to all rules —
    do NOT recurse inside hook methods.

    Call `self.report(line, col, message)` to emit a violation. noqa handling is
    automatic; do not call `has_noqa` directly unless you need multi-line annotation
    coverage and must pass explicit `noqa_lines`.
    """

    code: ClassVar[RuleCode]
    category: ClassVar[RuleCategory]
    summary: ClassVar[str]
    suggestion: ClassVar[str]
    bad_example: ClassVar[str]
    good_examples: ClassVar[list[str]]
    exemptions: ClassVar[str]  # optional prose; rendered as "## Automatic Exemptions" in docs

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
    ) -> None:
        """Emit a violation, automatically honouring noqa suppression."""
        lines_to_check = noqa_lines if noqa_lines is not None else [line]
        if has_noqa(list(self._context.source_lines), lines_to_check, self.code):
            return
        self.violations.append(
            Violation(
                code=self.code,
                message=message,
                path=self._context.path,
                line=line,
                col=col,
            ),
        )


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
