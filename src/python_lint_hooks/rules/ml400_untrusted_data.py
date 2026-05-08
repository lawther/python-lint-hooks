"""ML400 — unvalidated external data used without Pydantic validation.

Data loaded from external sources (json.loads, yaml.safe_load, etc.) is untrusted.
It must be validated against a Pydantic model before use. Accessing untrusted data
via indexing or .get() without first validating it risks shape mismatches and
unexpected runtime errors.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import ClassVar, cast

from python_lint_hooks.noqa import has_noqa
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, register
from python_lint_hooks.violation import Violation

_UNTRUSTED_FUNCS: frozenset[str] = frozenset({"loads", "load", "safe_load", "full_load", "literal_eval"})


@dataclass(frozen=True)
class _TaintInfo:
    is_tainted: bool
    source_node: ast.AST | None = None


@register
class ML400(Rule):
    code: ClassVar[str] = "ML400"
    category: ClassVar[RuleCategory] = RuleCategory.DATA_TRUST
    summary: ClassVar[str] = "Unvalidated external data used without Pydantic validation"
    suggestion: ClassVar[str] = "Validate with a Pydantic model before use"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._taint_stack: list[dict[str, _TaintInfo]] = [{}]
        self._flagged_sources: set[ast.AST] = set()

    # ------------------------------------------------------------------
    # Scope tracking — push/pop a taint scope on function entry/exit
    # ------------------------------------------------------------------

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._taint_stack.append({})

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._taint_stack.pop()

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Taint propagation
    # ------------------------------------------------------------------

    def enter_Assign(self, node: ast.Assign) -> None:
        is_untrusted = self._is_untrusted_source(node.value)
        source_node: ast.AST | None = node if is_untrusted else None

        if not is_untrusted and isinstance(node.value, ast.Name):
            info = self._get_taint_info(node.value.id)
            if info.is_tainted:
                is_untrusted = True
                source_node = info.source_node

        for target in node.targets:
            for name in _get_names(target):
                self._set_taint(name, is_untrusted, source_node)

    def enter_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            return
        is_untrusted = self._is_untrusted_source(node.value)
        source_node: ast.AST | None = node if is_untrusted else None

        if not is_untrusted and isinstance(node.value, ast.Name):
            info = self._get_taint_info(node.value.id)
            if info.is_tainted:
                is_untrusted = True
                source_node = info.source_node

        for name in _get_names(node.target):
            self._set_taint(name, is_untrusted, source_node)

    def enter_For(self, node: ast.For) -> None:
        is_tainted = self._is_untrusted_source(node.iter)
        source_node: ast.AST | None = node if is_tainted else None

        if not is_tainted and isinstance(node.iter, ast.Name):
            info = self._get_taint_info(node.iter.id)
            if info.is_tainted:
                is_tainted = True
                source_node = info.source_node

        for name in _get_names(node.target):
            self._set_taint(name, is_tainted, source_node)

    def enter_ListComp(self, node: ast.ListComp) -> None:
        self._handle_comprehension(node.generators)

    def enter_SetComp(self, node: ast.SetComp) -> None:
        self._handle_comprehension(node.generators)

    def enter_DictComp(self, node: ast.DictComp) -> None:
        self._handle_comprehension(node.generators)

    def enter_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._handle_comprehension(node.generators)

    def _handle_comprehension(self, generators: list[ast.comprehension]) -> None:
        for gen in generators:
            is_tainted = self._is_untrusted_source(gen.iter)
            source_node: ast.AST | None = gen.iter if is_tainted else None

            if not is_tainted and isinstance(gen.iter, ast.Name):
                info = self._get_taint_info(gen.iter.id)
                if info.is_tainted:
                    is_tainted = True
                    source_node = info.source_node

            if is_tainted:
                for name in _get_names(gen.target):
                    self._set_taint(name, True, source_node)

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

    def _report_ml400(self, name: str, usage_node: ast.AST) -> None:
        info = self._get_taint_info(name)
        if not info.is_tainted:
            return

        report_node = info.source_node if info.source_node else usage_node
        if report_node in self._flagged_sources:
            return

        if not hasattr(usage_node, "lineno") or not hasattr(report_node, "lineno"):
            return

        usage_lineno = cast(int, usage_node.lineno)
        report_lineno = cast(int, report_node.lineno)
        report_col = cast(int, getattr(report_node, "col_offset", 0))

        source_lines = list(self._context.source_lines)
        if has_noqa(source_lines, [usage_lineno], self.code) or has_noqa(source_lines, [report_lineno], self.code):
            return

        self._flagged_sources.add(report_node)
        if info.source_node:
            msg = f"Variable '{name}' assigned unvalidated data and used here; validate with Pydantic"
        else:
            msg = f"Untrusted data in '{name}' used without Pydantic validation"

        self.violations.append(
            Violation(
                code=self.code,
                message=msg,
                path=self._context.path,
                line=report_lineno,
                col=report_col + 1,
            )
        )

    def _get_taint_info(self, name: str) -> _TaintInfo:
        for scope in reversed(self._taint_stack):
            if name in scope:
                return scope[name]
        return _TaintInfo(False)

    def _set_taint(self, name: str, is_tainted: bool, source_node: ast.AST | None = None) -> None:
        self._taint_stack[-1][name] = _TaintInfo(is_tainted, source_node)

    def _is_untrusted_source(self, node: ast.AST | None) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and (func.attr in _UNTRUSTED_FUNCS or func.attr == "json"):
            return True
        return bool(isinstance(func, ast.Name) and func.id in _UNTRUSTED_FUNCS)


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
