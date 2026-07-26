from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML300(Rule):
    """Class defined inside a function.

    A common motivation is to signal that the class is a private implementation
    detail of the enclosing function — "it will never escape here". However,
    Python does not enforce this: the function can return the class directly,
    and any caller holding an instance can recover the class via ``type()``.
    The inner placement is a social contract, not a visibility guarantee.

    The ``_`` prefix convention already provides the same signal at module
    level with no ambiguity, and without the cost of nesting a class definition
    inside a function body (which interrupts the reader's flow through the
    function's logic).

    Move the class to module level and prefix it with ``_`` if it is not part
    of the public API.
    """

    code: ClassVar[RuleCode] = RuleCode.ML300
    category: ClassVar[RuleCategory] = RuleCategory.SCOPE
    summary: ClassVar[str] = "Class defined inside a function"
    suggestion: ClassVar[str] = "Move it to module level"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        if self._function_depth > 0:
            self.report(
                node.lineno,
                node.col_offset + 1,
                f"Class '{node.name}' defined inside a function",
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
# Placing the class inside the function looks like it limits visibility,
# but Python does not enforce this — the class can still escape via a
# return value, or be recovered from any instance via type().
# Use the _ prefix at module level instead.
def parse_config(raw: str) -> None:
    class _RawConfig:
        host: str = ""
        port: int = 0
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
# _ signals that this is a private implementation detail,
# with no readability cost inside parse_config.
class _RawConfig:
    host: str = ""
    port: int = 0

def parse_config(raw: str) -> None:
    ...
"""
    ]
