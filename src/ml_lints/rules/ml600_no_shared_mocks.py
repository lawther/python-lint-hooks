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


def _called_name(node: ast.expr) -> str | None:
    """Return the dotted callee name if `node` is `name(...)` or `a.b(...)`, else None."""
    return _dotted_name(node.func) if isinstance(node, ast.Call) else None


def _factory_call_name(node: ast.expr) -> str | None:
    """Return the callee's dotted name if `node` is `factory()()`, else None."""
    return None if not isinstance(node, ast.Call) else _called_name(node.func)


def _single_return_value(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    if len(func_def.body) != 1:
        return None
    (only,) = func_def.body
    return only.value if isinstance(only, ast.Return) and only.value is not None else None


def _class_method_single_returns(cls_def: ast.ClassDef) -> dict[str, ast.expr]:
    """Map `ClassName.method` to its single return expression, for `return X`-only methods."""
    returns: dict[str, ast.expr] = {}
    for stmt in cls_def.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            value = _single_return_value(stmt)
            if value is not None:
                returns[f"{cls_def.name}.{stmt.name}"] = value
    return returns


def _single_return_functions(module: ast.Module) -> dict[str, ast.expr]:
    """Map every function (top-level, or `Class.method`) whose body is `return X` to X.

    `@factory()(...)` calls the factory to get a decorator, then immediately calls the
    result; `new=factory()()` does the same to get a mock class. If the factory does
    nothing but hand back `patch` or a Mock/MagicMock/AsyncMock class unmodified, the
    result behaves exactly like using that value directly, including evaluating `new=`
    once at import time. A factory can itself be reached through another factory
    (`_get_patcher2` returning `_get_patcher()`), so every such function needs indexing
    up front — not just the ones that obviously return `patch` or a mock class — to let
    the resolver walk the whole chain.
    """
    returns: dict[str, ast.expr] = {}
    for stmt in module.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            value = _single_return_value(stmt)
            if value is not None:
                returns[stmt.name] = value
        elif isinstance(stmt, ast.ClassDef):
            returns.update(_class_method_single_returns(stmt))
    return returns


def _top_level_name_assigns(module: ast.Module) -> dict[str, ast.expr]:
    """Map every top-level `name = value` (or annotated) binding to its RHS value.

    A `new=` argument doesn't have to construct the mock inline — a bare name bound
    once at module scope is just as shared, since the binding (like the decorator's
    keyword arguments) is only ever evaluated at import time. The name doesn't have to
    be bound directly to the mock either (`a = AsyncMock()` then `b = a`); every binding
    is indexed so the resolver can follow an alias chain to whatever it ultimately
    points at.
    """
    assigns: dict[str, ast.expr] = {}
    for stmt in module.body:
        target: ast.expr
        value: ast.expr
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        else:
            continue
        if isinstance(target, ast.Name):
            assigns[target.id] = value
    return assigns


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
    instance at import time. Resolution isn't limited to one hop: a factory reached
    through another factory, a name aliasing another name, or a factory reached via a
    class attribute (`Helpers.get_patcher()`) are all followed to the end of the chain.

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
        self._name_assigns: dict[str, ast.expr] = {}
        self._factory_defs: dict[str, ast.expr] = {}

    def enter_Module(self, node: ast.Module) -> None:
        self._name_assigns = _top_level_name_assigns(node)
        self._factory_defs = _single_return_functions(node)

    def _resolve_mock_instance_class(self, name: str, seen: frozenset[str]) -> str | None:
        if name in seen:
            return None
        value = self._name_assigns.get(name)
        if value is None:
            return None
        mock_class = _mock_class_name(value)
        if mock_class is not None:
            return mock_class
        if isinstance(value, ast.Name):
            return self._resolve_mock_instance_class(value.id, seen | {name})
        return None

    def _resolve_patch_factory(self, name: str, seen: frozenset[str]) -> bool:
        if name in seen:
            return False
        value = self._factory_defs.get(name)
        if value is None:
            return False
        if _is_patch_call(value):
            return True
        inner = _called_name(value)
        return inner is not None and self._resolve_patch_factory(inner, seen | {name})

    def _resolve_mock_class_factory(self, name: str, seen: frozenset[str]) -> str | None:
        if name in seen:
            return None
        value = self._factory_defs.get(name)
        if value is None:
            return None
        dotted = _dotted_name(value)
        mock_class = None if dotted is None else _simple_mock_class_name(dotted)
        if mock_class is not None:
            return mock_class
        inner = _called_name(value)
        return None if inner is None else self._resolve_mock_class_factory(inner, seen | {name})

    def _resolve_mock_class(self, value: ast.expr) -> str | None:
        mock_class = _mock_class_name(value)
        if mock_class is not None:
            return mock_class
        if isinstance(value, ast.Name):
            return self._resolve_mock_instance_class(value.id, frozenset())
        factory_name = _factory_call_name(value)
        return None if factory_name is None else self._resolve_mock_class_factory(factory_name, frozenset())

    def _is_patch_decorator_call(self, deco: ast.Call) -> bool:
        if _is_patch_call(deco.func):
            return True
        factory_name = _factory_call_name(deco)
        return factory_name is not None and self._resolve_patch_factory(factory_name, frozenset())

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
