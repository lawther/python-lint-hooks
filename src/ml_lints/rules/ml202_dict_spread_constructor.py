"""ML202 — constructor called by spreading `.__dict__` or `vars()`.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import Rule, RuleCategory, RuleCode, register


def _is_dunder_dict(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "__dict__"


def _is_vars_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "vars"
        and len(node.args) == 1
        and not node.keywords
    )


def _is_instance_spread(node: ast.expr) -> bool:
    return _is_dunder_dict(node) or _is_vars_call(node)


def _spread_label(node: ast.expr) -> str:
    return ".__dict__" if _is_dunder_dict(node) else "vars()"


@register
class ML202(Rule):
    """Constructor called by spreading `.__dict__` or `vars()`.

    `Cls(**obj.__dict__)` and `Cls(**vars(obj))` are fragile ways to copy or
    derive a dataclass instance. They bypass `InitVar` fields, silently break
    with `field(init=False)`, and fail entirely on `__slots__`-based
    dataclasses. Use `dataclasses.replace(obj, field=value)` instead — the
    idiomatic, type-safe API designed for this purpose.
    """

    code: ClassVar[RuleCode] = RuleCode.ML202
    category: ClassVar[RuleCategory] = RuleCategory.CLASS_SHAPE
    summary: ClassVar[str] = "Constructor called by spreading `.__dict__` or `vars()`"
    suggestion: ClassVar[str] = "Use `dataclasses.replace(obj, field=value)` instead"

    def enter_Call(self, node: ast.Call) -> None:
        for kw in node.keywords:
            if kw.arg is not None:
                continue
            val = kw.value
            # Spelling 1 & 2: Cls(**obj.__dict__) or Cls(**vars(obj))
            if _is_instance_spread(val):
                self.report(
                    val.lineno,
                    val.col_offset + 1,
                    f"Use `dataclasses.replace()` instead of spreading `{_spread_label(val)}`",
                )
            # Spelling 3 & 4: Cls(**{**obj.__dict__, ...}) or Cls(**{**vars(obj), ...})
            elif isinstance(val, ast.Dict):
                for key, dict_val in zip(val.keys, val.values, strict=False):
                    if key is None and _is_instance_spread(dict_val):
                        self.report(
                            dict_val.lineno,
                            dict_val.col_offset + 1,
                            f"Use `dataclasses.replace()` instead of spreading `{_spread_label(dict_val)}`",
                        )
                        break

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
import dataclasses

@dataclasses.dataclass(frozen=True)
class Point:
    x: int
    y: int

p = Point(1, 2)
q = Point(**{**p.__dict__, "x": 10})
"""

    good_examples: ClassVar[list[str]] = [
        """
import dataclasses

@dataclasses.dataclass(frozen=True)
class Point:
    x: int
    y: int

p = Point(1, 2)
q = dataclasses.replace(p, x=10)
""",
    ]
