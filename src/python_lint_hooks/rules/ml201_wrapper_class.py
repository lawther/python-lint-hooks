"""ML201 — class contains only forbidden types.

A class where every annotated field is itself a forbidden type (bare dict, tuple, etc.)
offers no real abstraction — it just wraps the forbidden pattern. Replace the fields with
properly-typed attributes or refactor the class.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


def _is_classvar(annotation: ast.expr) -> bool:
    """Return True if the annotation is ClassVar or ClassVar[...] (bare or qualified)."""
    node = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    if isinstance(node, ast.Name):
        return node.id == "ClassVar"
    if isinstance(node, ast.Attribute):
        return node.attr == "ClassVar"
    return False


@register
class ML201(Rule):
    code: ClassVar[RuleCode] = RuleCode.ML201
    category: ClassVar[RuleCategory] = RuleCategory.CLASS_SHAPE
    summary: ClassVar[str] = "Class contains only forbidden types"
    suggestion: ClassVar[str] = "Use a proper abstraction with well-typed fields"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        annotations = [
            stmt for stmt in node.body if isinstance(stmt, ast.AnnAssign) and not _is_classvar(stmt.annotation)
        ]
        if not annotations:
            return

        for ann in annotations:
            analyzer = ForbiddenTypeAnalyzer()
            analyzer.analyze(ann.annotation)
            if not analyzer.findings:
                return  # at least one field is fine — class is ok

        self.report(
            node.lineno,
            node.col_offset + 1,
            f"Class '{node.name}' only contains forbidden types; use a proper abstraction",
        )
