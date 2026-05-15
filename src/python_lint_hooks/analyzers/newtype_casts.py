"""Shared analyzer for NewType cast hygiene rules (ML108, ML109).

Tracks the static NewType (and class) identity of names visible at a call site
and decides whether `T(x)` is a redundant cast. The analyzer is intentionally
conservative: when the static type of the argument cannot be resolved, the
call is left alone and the consuming rule emits no violation.
"""

from __future__ import annotations

import ast
import itertools
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from python_lint_hooks.analyzers.newtype_index import BuiltinBase

if TYPE_CHECKING:
    from python_lint_hooks.analyzers.newtype_index import NewTypeId, NewTypeIndex


_WIDENING_BUILTINS = frozenset({"str", "int", "float", "bool", "bytes", "bytearray", "complex"})


class CastKind(Enum):
    """How a `T(x)` call relates to the static type of its argument."""

    SELF = auto()  # T(x) where x is statically of type T (no-op)
    CROSS_SAME_BASE = auto()  # T(x) where x is statically of type U, U != T, same base


@dataclass(frozen=True)
class CastFinding:
    """Result of classifying a `T(x)` call."""

    kind: CastKind
    constructor: NewTypeId
    arg_newtype: NewTypeId
    line: int
    col: int


class NewTypeCastAnalyzer:
    """Scope-aware classifier for NewType cast calls within a single file.

    A rule instantiates one of these and forwards its enter_/leave_ hooks. When
    the rule's enter_Call hook fires, it calls classify_call() to get a CastFinding
    (or None) and decides whether to report.

    The analyzer maintains two parallel scope stacks:
      * NewType scopes: name → NewTypeId, for variables whose annotation is a NewType.
      * Class scopes: name → (defining_module, class_name), for variables whose
        annotation resolves to a known project class. Used to resolve `obj.attr`
        attribute accesses.
    """

    def __init__(self, module_path: str, index: NewTypeIndex) -> None:
        self._module = module_path
        self._index = index
        self._newtype_scopes: list[dict[str, NewTypeId]] = [{}]
        self._class_scopes: list[dict[str, tuple[str, str]]] = [{}]

    # ------------------------------------------------------------------
    # Scope tracking — driven by the rule's AST hooks
    # ------------------------------------------------------------------

    def enter_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        nt_scope: dict[str, NewTypeId] = {}
        cls_scope: dict[str, tuple[str, str]] = {}
        all_args = itertools.chain(
            node.args.posonlyargs,
            node.args.args,
            node.args.kwonlyargs,
        )
        for arg in all_args:
            self._record_arg_annotation(arg, nt_scope, cls_scope)
        if node.args.vararg is not None:
            self._record_arg_annotation(node.args.vararg, nt_scope, cls_scope)
        if node.args.kwarg is not None:
            self._record_arg_annotation(node.args.kwarg, nt_scope, cls_scope)
        self._newtype_scopes.append(nt_scope)
        self._class_scopes.append(cls_scope)

    def leave_function(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._newtype_scopes.pop()
        self._class_scopes.pop()

    def record_ann_assign(self, node: ast.AnnAssign) -> None:
        """Record `name: T = ...` annotations into the current scope."""
        if not isinstance(node.target, ast.Name):
            return
        self._record_name_annotation(node.target.id, node.annotation)

    # ------------------------------------------------------------------
    # Call classification
    # ------------------------------------------------------------------

    def classify_call(self, node: ast.Call) -> CastFinding | None:
        """Return a CastFinding if `node` is a redundant NewType cast.

        Returns None when:
          - the callee is not a known NewType,
          - the call uses keyword args or doesn't have exactly one positional arg,
          - the argument is a plain literal or an explicit widening call,
          - the argument's static type cannot be statically determined,
          - the constructor and argument NewTypes have different bases.
        """
        constructor = self._resolve_call_target(node)
        if constructor is None or node.keywords or len(node.args) != 1:
            return None
        arg = node.args[0]
        if self._is_literal(arg) or self._is_widening_call(arg):
            return None
        arg_identity = self._resolve_expression_type(arg)
        if arg_identity is None:
            return None

        if arg_identity == constructor:
            kind = CastKind.SELF
        else:
            ctor_base = self._index.canonical_base(constructor)
            arg_base = self._index.canonical_base(arg_identity)
            if ctor_base == BuiltinBase.UNKNOWN or ctor_base != arg_base:
                return None
            kind = CastKind.CROSS_SAME_BASE
        return CastFinding(kind, constructor, arg_identity, node.lineno, node.col_offset + 1)

    # ------------------------------------------------------------------
    # Internal resolution helpers
    # ------------------------------------------------------------------

    def _record_arg_annotation(
        self,
        arg: ast.arg,
        nt_scope: dict[str, NewTypeId],
        cls_scope: dict[str, tuple[str, str]],
    ) -> None:
        if arg.annotation is None:
            return
        nt = self._index.resolve_annotation(self._module, arg.annotation)
        if nt is not None:
            nt_scope[arg.arg] = nt
            return
        cls = self._resolve_class_annotation(arg.annotation)
        if cls is not None:
            cls_scope[arg.arg] = cls

    def _record_name_annotation(self, name: str, annotation: ast.expr) -> None:
        nt = self._index.resolve_annotation(self._module, annotation)
        if nt is not None:
            self._newtype_scopes[-1][name] = nt
            return
        cls = self._resolve_class_annotation(annotation)
        if cls is not None:
            self._class_scopes[-1][name] = cls

    def _resolve_class_annotation(self, annotation: ast.expr) -> tuple[str, str] | None:
        """If `annotation` is a Name referring to a known project class, return its (module, original_name)."""
        if not isinstance(annotation, ast.Name):
            return None
        return self._index.find_class_module(self._module, annotation.id)

    def _resolve_call_target(self, node: ast.Call) -> NewTypeId | None:
        func = node.func
        if isinstance(func, ast.Name):
            return self._index.resolve_local_name(self._module, func.id)
        return None

    def _resolve_expression_type(self, expr: ast.expr) -> NewTypeId | None:
        if isinstance(expr, ast.Name):
            return self._lookup_name(expr.id)
        if isinstance(expr, ast.Attribute):
            return self._resolve_attribute(expr)
        if isinstance(expr, ast.Call):
            return self._resolve_call_return(expr)
        return None

    def _lookup_name(self, name: str) -> NewTypeId | None:
        for scope in reversed(self._newtype_scopes):
            if name in scope:
                return scope[name]
        return None

    def _resolve_attribute(self, node: ast.Attribute) -> NewTypeId | None:
        if not isinstance(node.value, ast.Name):
            return None
        owner_class = self._lookup_class_for_name(node.value.id)
        if owner_class is None:
            return None
        class_module, class_name = owner_class
        return self._index.lookup_class_field(class_module, class_name, node.attr)

    def _lookup_class_for_name(self, name: str) -> tuple[str, str] | None:
        for scope in reversed(self._class_scopes):
            if name in scope:
                return scope[name]
        return None

    def _resolve_call_return(self, node: ast.Call) -> NewTypeId | None:
        if not isinstance(node.func, ast.Name):
            return None
        target = self._index.find_function_module(self._module, node.func.id)
        if target is None:
            return None
        defining_module, original_name = target
        return self._index.lookup_function_return(defining_module, original_name)

    def _is_literal(self, expr: ast.expr) -> bool:
        return isinstance(expr, ast.Constant)

    def _is_widening_call(self, expr: ast.expr) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        func = expr.func
        return isinstance(func, ast.Name) and func.id in _WIDENING_BUILTINS
