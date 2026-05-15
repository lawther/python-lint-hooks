"""Shared AST-hook scaffolding for ML108 and ML109.

Both rules walk the same scopes (functions, for-loops, comprehensions) and
share the same call-classification logic via NewTypeCastAnalyzer. This
module owns the hook delegation so the concrete rule files only have to
say which CastKind they care about and how to phrase the violation.

Filename is prefixed with `_` so the rule auto-discovery in
`python_lint_hooks.rules.__init__` skips it.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from python_lint_hooks.analyzers.newtype_casts import CastFinding, NewTypeCastAnalyzer
from python_lint_hooks.rules import CheckContext, Rule

if TYPE_CHECKING:
    pass


class NewTypeCastRuleBase(Rule):
    """Base class for rules that consume NewTypeCastAnalyzer."""

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._analyzer: NewTypeCastAnalyzer | None = None
        if context.project_index is not None:
            self._analyzer = NewTypeCastAnalyzer(str(context.path.resolve()), context.project_index)

    # ------------------------------------------------------------------
    # Function scope
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._analyzer is not None:
            self._analyzer.enter_function(node)

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._analyzer is not None:
            self._analyzer.leave_function(node)

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Local annotation tracking
    # ------------------------------------------------------------------

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._analyzer is not None:
            self._analyzer.record_ann_assign(node)

    # ------------------------------------------------------------------
    # For / async-for scope
    # ------------------------------------------------------------------

    def enter_For(self, node: ast.For) -> None:
        if self._analyzer is not None:
            self._analyzer.enter_for(node)

    def leave_For(self, node: ast.For) -> None:
        if self._analyzer is not None:
            self._analyzer.leave_for(node)

    enter_AsyncFor = enter_For  # type: ignore[assignment]
    leave_AsyncFor = leave_For  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Comprehension scopes
    # ------------------------------------------------------------------

    def enter_ListComp(self, node: ast.ListComp) -> None:
        if self._analyzer is not None:
            self._analyzer.enter_comprehension(node)

    def leave_ListComp(self, node: ast.ListComp) -> None:
        if self._analyzer is not None:
            self._analyzer.leave_comprehension(node)

    enter_SetComp = enter_ListComp  # type: ignore[assignment]
    leave_SetComp = leave_ListComp  # type: ignore[assignment]
    enter_DictComp = enter_ListComp  # type: ignore[assignment]
    leave_DictComp = leave_ListComp  # type: ignore[assignment]
    enter_GeneratorExp = enter_ListComp  # type: ignore[assignment]
    leave_GeneratorExp = leave_ListComp  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Call classification — subclass picks which kind to act on
    # ------------------------------------------------------------------

    def enter_Call(self, node: ast.Call) -> None:
        if self._analyzer is None:
            return
        finding = self._analyzer.classify_call(node)
        if finding is None:
            return
        self._handle_finding(finding)

    def _handle_finding(self, finding: CastFinding) -> None:
        raise NotImplementedError
