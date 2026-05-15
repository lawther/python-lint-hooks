"""Shared analyzer for NewType cast hygiene rules (ML108, ML109).

Tracks the static type of names visible at a call site and decides whether
`T(x)` is a redundant cast. The analyzer is intentionally conservative:
when the static type of the argument cannot be resolved, the call is left
alone and the consuming rule emits no violation.

Internally, the analyzer keeps a stack of scopes (one per function or
comprehension layer). Each scope maps a local name to a `ResolvedType`
that records what the name statically refers to: a NewType identity, a
project class identity, an iterable whose elements are one of those, or
nothing recognised. Resolution happens eagerly when a name is bound — at
that moment we know which module's namespace the annotation belongs to.
Looking the name up later is then a simple scope walk with no further
namespace bookkeeping.
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

# Containers whose generic single parameter is the iteration element.
_SINGLE_PARAM_ITERABLES = frozenset(
    {
        "list",
        "List",
        "set",
        "Set",
        "frozenset",
        "FrozenSet",
        "Iterable",
        "Iterator",
        "AsyncIterable",
        "AsyncIterator",
        "Sequence",
        "MutableSequence",
        "Collection",
        "Reversible",
        "Container",
    }
)

# Containers whose first generic parameter is the iteration element (mappings).
_MAPPING_ITERABLES = frozenset({"dict", "Dict", "Mapping", "MutableMapping"})

# Containers requiring tuple[T, ...] form (homogeneous variadic tuple).
_TUPLE_NAMES = frozenset({"tuple", "Tuple"})


def _extract_homogeneous_tuple_element(slice_expr: ast.expr) -> ast.expr | None:
    """Return T from a `tuple[T, ...]` slice expression; None for fixed-arity tuples."""
    min_homogeneous_tuple_arity = 2
    if not isinstance(slice_expr, ast.Tuple) or len(slice_expr.elts) != min_homogeneous_tuple_arity:
        return None
    second = slice_expr.elts[1]
    if isinstance(second, ast.Constant) and second.value is Ellipsis:
        return slice_expr.elts[0]
    return None


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


@dataclass(frozen=True)
class ResolvedType:
    """A name's statically-known type, resolved in the namespace it was bound under.

    Exactly one of the four fields is populated when the resolution succeeded;
    the all-None instance represents an unresolved type (which the analyzer
    treats as "we don't know — don't flag anything").
    """

    newtype: NewTypeId | None = None
    class_id: tuple[str, str] | None = None
    iter_elem_newtype: NewTypeId | None = None
    iter_elem_class: tuple[str, str] | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.newtype is None
            and self.class_id is None
            and self.iter_elem_newtype is None
            and self.iter_elem_class is None
        )


_EMPTY = ResolvedType()


class NewTypeCastAnalyzer:
    """Scope-aware classifier for NewType cast calls within a single file."""

    def __init__(self, module_path: str, index: NewTypeIndex) -> None:
        self._module = module_path
        self._index = index
        # Stack of {name: ResolvedType}. Bottom layer is module scope.
        self._scopes: list[dict[str, ResolvedType]] = [{}]

    # ------------------------------------------------------------------
    # Scope tracking — driven by the rule's AST hooks
    # ------------------------------------------------------------------

    def enter_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        scope: dict[str, ResolvedType] = {}
        all_args = itertools.chain(
            node.args.posonlyargs,
            node.args.args,
            node.args.kwonlyargs,
        )
        for arg in all_args:
            self._bind_arg(arg, scope)
        if node.args.vararg is not None:
            self._bind_arg(node.args.vararg, scope)
        if node.args.kwarg is not None:
            self._bind_arg(node.args.kwarg, scope)
        self._scopes.append(scope)

    def leave_function(self, _node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scopes.pop()

    def record_ann_assign(self, node: ast.AnnAssign) -> None:
        if not isinstance(node.target, ast.Name):
            return
        resolved = self._resolve_in_module(self._module, node.annotation)
        if not resolved.is_empty:
            self._scopes[-1][node.target.id] = resolved

    def enter_for(self, node: ast.For | ast.AsyncFor) -> None:
        scope: dict[str, ResolvedType] = {}
        self._bind_iterable_target(node.iter, node.target, scope)
        self._scopes.append(scope)

    def leave_for(self, _node: ast.For | ast.AsyncFor) -> None:
        self._scopes.pop()

    def enter_comprehension(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        scope: dict[str, ResolvedType] = {}
        for gen in node.generators:
            self._bind_iterable_target(gen.iter, gen.target, scope)
        self._scopes.append(scope)

    def leave_comprehension(
        self,
        _node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        self._scopes.pop()

    # ------------------------------------------------------------------
    # Call classification
    # ------------------------------------------------------------------

    def classify_call(self, node: ast.Call) -> CastFinding | None:
        """Return a CastFinding if `node` is a redundant NewType cast.

        Returns None when:
          - the callee is not a known NewType,
          - the call uses keyword args or doesn't have exactly one positional arg,
          - the argument is a plain literal or an explicit widening call,
          - the argument's static type cannot be determined,
          - the constructor and argument NewTypes have different bases.
        """
        constructor = self._resolve_call_target(node)
        if constructor is None or node.keywords or len(node.args) != 1:
            return None
        arg = node.args[0]
        if self._is_literal(arg) or self._is_widening_call(arg):
            return None
        arg_resolved = self._resolve_expression(arg)
        arg_identity = arg_resolved.newtype
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
    # Binding helpers
    # ------------------------------------------------------------------

    def _bind_arg(self, arg: ast.arg, scope: dict[str, ResolvedType]) -> None:
        if arg.annotation is None:
            return
        resolved = self._resolve_in_module(self._module, arg.annotation)
        if not resolved.is_empty:
            scope[arg.arg] = resolved

    def _bind_iterable_target(
        self,
        iter_expr: ast.expr,
        target: ast.expr,
        scope: dict[str, ResolvedType],
    ) -> None:
        if not isinstance(target, ast.Name):
            return
        container = self._resolve_expression(iter_expr)
        element = ResolvedType(
            newtype=container.iter_elem_newtype,
            class_id=container.iter_elem_class,
        )
        if not element.is_empty:
            scope[target.id] = element

    # ------------------------------------------------------------------
    # Resolution: expression → ResolvedType
    # ------------------------------------------------------------------

    def _resolve_expression(self, expr: ast.expr) -> ResolvedType:
        if isinstance(expr, ast.Name):
            return self._lookup_name(expr.id)
        if isinstance(expr, ast.Attribute):
            return self._resolve_attribute(expr)
        if isinstance(expr, ast.Call):
            return self._resolve_call(expr)
        return _EMPTY

    def _lookup_name(self, name: str) -> ResolvedType:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return _EMPTY

    def _resolve_attribute(self, node: ast.Attribute) -> ResolvedType:
        owner = self._resolve_expression(node.value)
        if owner.class_id is None:
            return _EMPTY
        class_module, class_name = owner.class_id
        annotation = self._index.get_class_field_annotation(class_module, class_name, node.attr)
        if annotation is None:
            return _EMPTY
        return self._resolve_in_module(class_module, annotation)

    def _resolve_call(self, node: ast.Call) -> ResolvedType:
        if not isinstance(node.func, ast.Name):
            return _EMPTY
        target = self._index.find_function_module(self._module, node.func.id)
        if target is None:
            return _EMPTY
        defining_module, original_name = target
        annotation = self._index.get_function_return_annotation(defining_module, original_name)
        if annotation is None:
            return _EMPTY
        return self._resolve_in_module(defining_module, annotation)

    def _resolve_call_target(self, node: ast.Call) -> NewTypeId | None:
        func = node.func
        if isinstance(func, ast.Name):
            return self._index.resolve_local_name(self._module, func.id)
        return None

    # ------------------------------------------------------------------
    # Resolution: annotation expression in some module's namespace
    # ------------------------------------------------------------------

    def _resolve_in_module(self, namespace_module: str, annotation: ast.expr) -> ResolvedType:
        """Resolve an annotation expression in the namespace of `namespace_module`.

        Recognises three forms:
          * a bare Name that is a project NewType,
          * a bare Name that is a project class,
          * a Subscript over a recognised iterable container whose element is one of
            the two above.
        """
        if isinstance(annotation, ast.Name):
            return self._resolve_name_in_module(namespace_module, annotation.id)
        if isinstance(annotation, ast.Subscript):
            element_annotation = self._extract_element_annotation(annotation)
            if element_annotation is None:
                return _EMPTY
            inner = self._resolve_in_module(namespace_module, element_annotation)
            if inner.newtype is not None:
                return ResolvedType(iter_elem_newtype=inner.newtype)
            if inner.class_id is not None:
                return ResolvedType(iter_elem_class=inner.class_id)
            return _EMPTY
        return _EMPTY

    def _resolve_name_in_module(self, namespace_module: str, name: str) -> ResolvedType:
        newtype = self._index.resolve_local_name(namespace_module, name)
        if newtype is not None:
            return ResolvedType(newtype=newtype)
        class_id = self._index.find_class_module(namespace_module, name)
        if class_id is not None:
            return ResolvedType(class_id=class_id)
        return _EMPTY

    @staticmethod
    def _extract_element_annotation(annotation: ast.Subscript) -> ast.expr | None:
        if not isinstance(annotation.value, ast.Name):
            return None
        container = annotation.value.id
        slice_expr = annotation.slice
        if container in _SINGLE_PARAM_ITERABLES:
            return slice_expr
        if container in _MAPPING_ITERABLES:
            return slice_expr.elts[0] if isinstance(slice_expr, ast.Tuple) and slice_expr.elts else None
        if container in _TUPLE_NAMES:
            return _extract_homogeneous_tuple_element(slice_expr)
        return None

    @staticmethod
    def _is_literal(expr: ast.expr) -> bool:
        return isinstance(expr, ast.Constant)

    @staticmethod
    def _is_widening_call(expr: ast.expr) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        func = expr.func
        return isinstance(func, ast.Name) and func.id in _WIDENING_BUILTINS
