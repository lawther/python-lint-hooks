"""ML600 — `@patch(..., new=Mock(...))` shares one mock instance across every test.

See CONTRIBUTING_RULES.md for the full rule-writing guide.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register

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


def _simple_mock_class_name(name: str) -> str | None:
    simple = name.rsplit(".", maxsplit=1)[-1]
    return simple if simple in _MOCK_CLASS_NAMES else None


def _mock_class_name(value: ast.expr) -> str | None:
    if not isinstance(value, ast.Call):
        return None
    name = _dotted_name(value.func)
    return None if name is None else _simple_mock_class_name(name)


def _factory_call_name(node: ast.expr) -> str | None:
    """Return the factory's name if `node` is `factory()()`, else None."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Call):
        return None
    factory = node.func.func
    return factory.id if isinstance(factory, ast.Name) else None


def _single_return_value(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    if len(func_def.body) != 1:
        return None
    (only,) = func_def.body
    return only.value if isinstance(only, ast.Return) and only.value is not None else None


def _module_level_patch_factories(module: ast.Module) -> frozenset[str]:
    """Names of top-level functions whose entire body is `return patch` (or equivalent).

    `@factory()(...)` calls the factory to get a decorator, then immediately calls the
    result. If the factory does nothing but hand back `patch` (or `mock.patch.object`,
    etc.) unmodified, the produced decorator behaves exactly like `patch` itself,
    including evaluating `new=` once at import time.
    """
    factories: set[str] = set()
    for stmt in module.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            value = _single_return_value(stmt)
            if value is not None and _is_patch_call(value):
                factories.add(stmt.name)
    return frozenset(factories)


def _module_level_mock_class_factories(module: ast.Module) -> dict[str, str]:
    """Map top-level functions whose entire body is `return MockClass` to that class name.

    `new=factory()()` calls the factory to get a mock class, then instantiates it. If the
    factory does nothing but hand back a Mock/MagicMock/AsyncMock class, the result is
    exactly `new=MockClass()` — still built once, still shared.
    """
    factories: dict[str, str] = {}
    for stmt in module.body:
        if not isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        value = _single_return_value(stmt)
        if value is None:
            continue
        name = _dotted_name(value)
        mock_class = None if name is None else _simple_mock_class_name(name)
        if mock_class is not None:
            factories[stmt.name] = mock_class
    return factories


def _module_level_mock_names(module: ast.Module) -> dict[str, str]:
    """Map top-level `name = Mock(...)` bindings to their mock class name.

    A `new=` argument doesn't have to construct the mock inline — a bare name
    bound once at module scope is just as shared, since the binding (like the
    decorator's keyword arguments) is only ever evaluated at import time.
    """
    mock_names: dict[str, str] = {}
    for stmt in module.body:
        target: ast.expr
        value: ast.expr
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        mock_class = _mock_class_name(value)
        if mock_class is not None:
            mock_names[target.id] = mock_class
    return mock_names


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

    This also catches `new=` pointing at a bare name bound to a mock instance
    at module scope (`shared = AsyncMock()` then `@patch(..., new=shared)`) —
    that binding is evaluated once too, so it's exactly as shared.

    It also sees through a decorator factory that does nothing but hand back
    `patch` (`def _get_patcher(): return patch` then `@_get_patcher()(..., new=Mock())`)
    — the produced decorator behaves exactly like `patch` itself. The same applies on
    the `new=` side: a factory that just hands back a mock class
    (`def _get_cls(): return AsyncMock` then `new=_get_cls()()`) still builds one
    instance at import time.

    Note this only applies to the decorator form. `with patch(..., new=Mock()):`
    inside a function body is fine — that expression re-evaluates on every
    call, so each test gets its own instance.
    """

    code: ClassVar[RuleCode] = RuleCode.ML600
    category: ClassVar[RuleCategory] = RuleCategory.TESTING
    summary: ClassVar[str] = "`@patch(new=Mock(...))` shares one mock instance across tests"
    suggestion: ClassVar[str] = "Use `new_callable=Mock` (or `MagicMock`/`AsyncMock`) instead"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._module_mocks: dict[str, str] = {}
        self._patch_factories: frozenset[str] = frozenset()
        self._mock_class_factories: dict[str, str] = {}

    def enter_Module(self, node: ast.Module) -> None:
        self._module_mocks = _module_level_mock_names(node)
        self._patch_factories = _module_level_patch_factories(node)
        self._mock_class_factories = _module_level_mock_class_factories(node)

    def _resolve_mock_class(self, value: ast.expr) -> str | None:
        mock_class = _mock_class_name(value)
        if mock_class is not None:
            return mock_class
        if isinstance(value, ast.Name):
            return self._module_mocks.get(value.id)
        factory_name = _factory_call_name(value)
        return None if factory_name is None else self._mock_class_factories.get(factory_name)

    def _is_patch_decorator_call(self, deco: ast.Call) -> bool:
        if _is_patch_call(deco.func):
            return True
        factory_name = _factory_call_name(deco)
        return factory_name is not None and factory_name in self._patch_factories

    def _check_decorators(self, decorator_list: list[ast.expr]) -> None:
        for deco in decorator_list:
            if not isinstance(deco, ast.Call) or not self._is_patch_decorator_call(deco):
                continue
            for kw in deco.keywords:
                if kw.arg != "new":
                    continue
                mock_class = self._resolve_mock_class(kw.value)
                if mock_class is None:
                    continue
                self.report(
                    kw.value.lineno,
                    kw.value.col_offset + 1,
                    f"@patch(new={ast.unparse(kw.value)}) shares one instance across every "
                    f"test; use new_callable={mock_class} instead",
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
