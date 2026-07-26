"""ML600 — `@patch(..., new=Mock(...))` shares one mock instance across every test.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import Rule, RuleCategory, RuleCode, register

_PATCH_CALL_SUFFIXES = ("patch", "patch.object", "patch.multiple")
_MOCK_CLASS_NAMES = frozenset({"Mock", "MagicMock", "AsyncMock"})


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _is_patch_call(func: ast.expr) -> bool:
    name = _dotted_name(func)
    if name is None:
        return False
    return any(name == suffix or name.endswith(f".{suffix}") for suffix in _PATCH_CALL_SUFFIXES)


def _mock_class_name(value: ast.expr) -> str | None:
    if not isinstance(value, ast.Call):
        return None
    name = _dotted_name(value.func)
    if name is None:
        return None
    simple = name.rsplit(".", maxsplit=1)[-1]
    return simple if simple in _MOCK_CLASS_NAMES else None


@register
class ML600(Rule):
    """`@patch(..., new=Mock(...))` shares one mock instance across every test.

    A decorator's arguments are evaluated once, at module import time — not
    per test call. `@patch(..., new=AsyncMock())` (and the `MagicMock`/`Mock`
    equivalents) therefore builds a single instance and injects that same
    object into every test decorated with it. Call counts, side effects, and
    return values persist across tests, breaking isolation and causing
    order-dependent flakes.

    `new_callable=AsyncMock` passes the class itself; `patch` calls it fresh
    before each test and discards the instance afterwards, so tests stay
    isolated. Use `new_callable=` instead.

    Note this only applies to the decorator form. `with patch(..., new=Mock()):`
    inside a function body is fine — that expression re-evaluates on every
    call, so each test gets its own instance.
    """

    code: ClassVar[RuleCode] = RuleCode.ML600
    category: ClassVar[RuleCategory] = RuleCategory.TESTING
    summary: ClassVar[str] = "`@patch(new=Mock(...))` shares one mock instance across tests"
    suggestion: ClassVar[str] = "Use `new_callable=Mock` (or `MagicMock`/`AsyncMock`) instead"

    def _check_decorators(self, decorator_list: list[ast.expr]) -> None:
        for deco in decorator_list:
            if not isinstance(deco, ast.Call) or not _is_patch_call(deco.func):
                continue
            for kw in deco.keywords:
                if kw.arg != "new":
                    continue
                mock_class = _mock_class_name(kw.value)
                if mock_class is None:
                    continue
                self.report(
                    kw.value.lineno,
                    kw.value.col_offset + 1,
                    f"@patch(new={mock_class}(...)) shares one instance across every test; "
                    f"use new_callable={mock_class} instead",
                )

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._check_decorators(node.decorator_list)

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_decorators(node.decorator_list)

    enter_AsyncFunctionDef = enter_FunctionDef

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
from unittest.mock import AsyncMock, patch

@patch("api.client.send", new=AsyncMock())
def test_send(mock_send: AsyncMock) -> None:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
from unittest.mock import AsyncMock, patch

@patch("api.client.send", new_callable=AsyncMock)
def test_send(mock_send: AsyncMock) -> None:
    ...
""",
        """
from unittest.mock import MagicMock, patch

def test_send() -> None:
    with patch("api.client.send", new=MagicMock(return_value=1)):
        ...
""",
    ]
