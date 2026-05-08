"""ML105 — NewType wraps a forbidden type.

`NewType("Foo", dict[str, str])` looks like a distinct type but it is really just a
bare dict at runtime. Wrapping a forbidden type in a NewType does not make it acceptable;
use a dataclass or NamedTuple instead.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


def _is_newtype_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "NewType") or (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "typing"
        and func.attr == "NewType"
    )


@register
class ML105(Rule):
    code: ClassVar[RuleCode] = RuleCode.ML105
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "`NewType` wraps a forbidden type"
    suggestion: ClassVar[str] = "Use a dataclass or NamedTuple instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)

    def enter_Call(self, node: ast.Call) -> None:
        if not _is_newtype_call(node) or len(node.args) < 2:  # noqa: PLR2004
            return

        wrapped_type = node.args[1]
        analyzer = ForbiddenTypeAnalyzer()
        analyzer.analyze(wrapped_type)
        if not analyzer.findings:
            return

        newtype_name = "unknown"
        if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            newtype_name = node.args[0].value

        self.report(
            node.lineno,
            node.col_offset + 1,
            f"NewType '{newtype_name}' wraps a forbidden type; use a dataclass or NamedTuple instead",
        )
