from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


def _is_dataclass_decorator(decorator: ast.expr) -> bool:
    """Return True if the decorator is @dataclass or @dataclasses.dataclass (bare or called)."""
    node = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(node, ast.Name):
        return node.id == "dataclass"
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.attr == "dataclass"
    return False


def _is_frozen(decorator: ast.Call) -> bool:
    return any(
        kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in decorator.keywords
    )


@register
class ML200(Rule):
    """Dataclass is not frozen.

    Mutable dataclasses can be accidentally modified after construction, which
    makes them harder to reason about and prevents them from being used in sets
    or as dictionary keys. Use `@dataclass(frozen=True)` to make instances
    immutable and hashable.
    """

    code: ClassVar[RuleCode] = RuleCode.ML200
    category: ClassVar[RuleCategory] = RuleCategory.CLASS_SHAPE
    summary: ClassVar[str] = "Dataclass is not frozen"
    suggestion: ClassVar[str] = "Use `@dataclass(frozen=True)`"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            if not _is_dataclass_decorator(decorator):
                continue
            frozen = isinstance(decorator, ast.Call) and _is_frozen(decorator)
            if not frozen:
                self.report(
                    decorator.lineno,
                    decorator.col_offset + 1,
                    f"Dataclass '{node.name}' is not frozen; use @dataclass(frozen=True)",
                )
            break

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
@dataclass
class User:
    id: int
    name: str
"""

    good_examples: ClassVar[list[str]] = [
        """
@dataclass(frozen=True)
class User:
    id: int
    name: str
"""
    ]
