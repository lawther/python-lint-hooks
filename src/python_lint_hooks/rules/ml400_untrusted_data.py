from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import ClassVar

from python_lint_hooks.noqa import has_noqa
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register
from python_lint_hooks.violation import Violation

_UNTRUSTED_FUNCS: frozenset[str] = frozenset({"loads", "load", "safe_load", "full_load", "literal_eval"})


@dataclass(frozen=True)
class _Tainted:
    """A variable is tainted; source_node is the AST node where the taint originates."""

    source_node: ast.stmt | ast.expr


@register
class ML400(Rule):
    """Unvalidated external data used without Pydantic validation.

    Data loaded from external sources (json.loads, yaml.safe_load, etc.) is
    untrusted and has an unknown shape. Accessing this data via indexing or
    `.get()` without first validating it risks `KeyError`, `AttributeError`,
    and unexpected runtime failures. Use a Pydantic model to validate the
    data shape at the boundary.
    """

    code: ClassVar[RuleCode] = RuleCode.ML400
    category: ClassVar[RuleCategory] = RuleCategory.DATA_TRUST
    summary: ClassVar[str] = "Unvalidated external data used without Pydantic validation"
    suggestion: ClassVar[str] = "Validate with a Pydantic model before use"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._taint_stack: list[dict[str, _Tainted | None]] = [{}]
        self._flagged_sources: set[ast.AST] = set()

    # ------------------------------------------------------------------
    # Scope tracking — push/pop a taint scope on function/comprehension entry/exit
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._taint_stack.append({})

    def leave_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._taint_stack.pop()

    enter_AsyncFunctionDef = enter_FunctionDef
    leave_AsyncFunctionDef = leave_FunctionDef

    def enter_ListComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._taint_stack.append({})
        self._handle_comprehension(node.generators)

    def leave_ListComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._taint_stack.pop()

    enter_SetComp = enter_ListComp
    leave_SetComp = leave_ListComp
    enter_DictComp = enter_ListComp
    leave_DictComp = leave_ListComp
    enter_GeneratorExp = enter_ListComp
    leave_GeneratorExp = leave_ListComp

    # ------------------------------------------------------------------
    # Taint propagation
    # ------------------------------------------------------------------

    def enter_Assign(self, node: ast.Assign) -> None:
        taint = self._taint_from(node.value, node)
        for target in node.targets:
            for name in _get_names(target):
                self._set_taint(name, taint)

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        taint = self._taint_from(node.value, node)
        for name in _get_names(node.target):
            self._set_taint(name, taint)

    def enter_For(self, node: ast.For) -> None:
        taint = self._taint_from(node.iter, node)
        for name in _get_names(node.target):
            self._set_taint(name, taint)

    def _handle_comprehension(self, generators: list[ast.comprehension]) -> None:
        for gen in generators:
            taint = self._taint_from(gen.iter, gen.iter)
            for name in _get_names(gen.target):
                self._set_taint(name, taint)

    def _taint_from(self, value: ast.AST, source: ast.stmt | ast.expr) -> _Tainted | None:
        """Return _Tainted(source) if value is an untrusted call, propagate if a tainted name, else None."""
        if self._is_untrusted_source(value):
            return _Tainted(source)
        if isinstance(value, ast.Name):
            return self._get_taint(value.id)
        return None

    # ------------------------------------------------------------------
    # Usage detection — subscript and .get() access on tainted names
    # ------------------------------------------------------------------

    def enter_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name):
            self._report_ml400(node.value.id, node)

    def enter_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and isinstance(node.func.value, ast.Name):
            self._report_ml400(node.func.value.id, node)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _report_ml400(self, name: str, usage_node: ast.expr) -> None:
        taint = self._get_taint(name)
        if taint is None:
            return

        report_node = taint.source_node
        if report_node in self._flagged_sources:
            return

        usage_lineno = usage_node.lineno
        report_lineno = report_node.lineno
        report_col = report_node.col_offset

        source_lines = list(self._context.source_lines)
        if has_noqa(source_lines, [usage_lineno], self.code) or has_noqa(source_lines, [report_lineno], self.code):
            return

        self._flagged_sources.add(report_node)
        self.violations.append(
            Violation(
                code=self.code,
                message=f"Variable '{name}' assigned unvalidated data and used here; validate with Pydantic",
                path=self._context.path,
                line=report_lineno,
                col=report_col + 1,
            )
        )

    def _get_taint(self, name: str) -> _Tainted | None:
        for scope in reversed(self._taint_stack):
            if name in scope:
                return scope[name]
        return None

    def _set_taint(self, name: str, taint: _Tainted | None) -> None:
        self._taint_stack[-1][name] = taint

    def _is_untrusted_source(self, node: ast.AST | None) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and (func.attr in _UNTRUSTED_FUNCS or func.attr == "json"):
            return True
        return bool(isinstance(func, ast.Name) and func.id in _UNTRUSTED_FUNCS)

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def get_config_timeout(path: Path):
    with open(path) as f:
        data = json.load(f)
    return data["timeout"]
"""

    good_examples: ClassVar[list[str]] = [
        """
class Config(BaseModel):
    timeout: int

def get_config_timeout(path: Path):
    with open(path) as f:
        config = Config.model_validate(json.load(f))
    return config.timeout
"""
    ]


def _get_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in node.elts:
            names.extend(_get_names(elt))
        return names
    if isinstance(node, ast.Starred):
        return _get_names(node.value)
    return []
