"""Cross-file index of NewType definitions and annotated symbols.

Built by a project-wide pre-pass before any per-file rule runs. Consumed by
ML108 and ML109 to determine whether a `T(x)` call is a redundant NewType
cast — those rules need to know:

* whether `T` is a NewType (and if so, its canonical base type),
* the static type of `x` when `x` is an attribute access into a class
  defined elsewhere in the project, or a call to a function defined
  elsewhere.

The index stays deliberately conservative. If a name cannot be resolved
through import chains, top-level definitions, or simple `Name`-form
annotations, the index returns `None` and the rule stays silent.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum, auto


class BuiltinBase(Enum):
    """Canonical base type for a NewType after chain resolution."""

    STR = auto()
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    BYTES = auto()
    BYTEARRAY = auto()
    COMPLEX = auto()
    UNKNOWN = auto()


_BUILTIN_BASE_NAMES: dict[str, BuiltinBase] = {
    "str": BuiltinBase.STR,
    "int": BuiltinBase.INT,
    "float": BuiltinBase.FLOAT,
    "bool": BuiltinBase.BOOL,
    "bytes": BuiltinBase.BYTES,
    "bytearray": BuiltinBase.BYTEARRAY,
    "complex": BuiltinBase.COMPLEX,
}


@dataclass(frozen=True)
class NewTypeId:
    """Stable identity for a NewType across the project."""

    module: str  # canonical module key (typically absolute file path)
    name: str  # local name in the defining module


@dataclass
class _ModuleInfo:
    """Everything ingested for a single module before finalisation."""

    path: str
    aliases: dict[str, tuple[str, str]] = field(default_factory=dict)
    """local_name → (origin_module_path or '<external>', original_name)"""

    newtype_base_expr: dict[str, ast.expr] = field(default_factory=dict)
    """local_name → the second-argument expression of NewType(...)"""

    class_field_annotations: dict[str, dict[str, ast.expr]] = field(default_factory=dict)
    """class_name → {field_name: annotation expression}"""

    function_returns: dict[str, ast.expr] = field(default_factory=dict)
    """top-level function name → return annotation expression"""


class _ModuleIngestor(ast.NodeVisitor):
    """Single-pass visitor that fills a _ModuleInfo from a parsed AST.

    Only top-level definitions are recorded. Nested NewTypes, classes, and
    functions are deliberately ignored — they are implementation details
    and cannot participate in cross-module resolution.
    """

    def __init__(self, info: _ModuleInfo) -> None:
        self._info = info

    def visit_Module(self, node: ast.Module) -> None:
        for child in node.body:
            self._handle_top_level(child)

    def _handle_top_level(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Import):
            self._record_plain_import(node)
        elif isinstance(node, ast.ImportFrom):
            self._record_from_import(node)
        elif isinstance(node, ast.Assign):
            self._maybe_record_newtype(node)
        elif isinstance(node, ast.ClassDef):
            self._record_class(node)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns is not None:
            self._info.function_returns[node.name] = node.returns

    def _record_plain_import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self._info.aliases[local] = ("<external>", alias.name)

    def _record_from_import(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            self._info.aliases[local] = (node.module, alias.name)

    def _maybe_record_newtype(self, node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return
        value = node.value
        if not isinstance(value, ast.Call):
            return
        if not _call_is_newtype(value):
            return
        # NewType("Name", base) — we only care about the base expression.
        min_newtype_args = 2
        if len(value.args) < min_newtype_args:
            return
        target_name = node.targets[0].id
        self._info.newtype_base_expr[target_name] = value.args[1]

    def _record_class(self, node: ast.ClassDef) -> None:
        fields: dict[str, ast.expr] = {}
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields[stmt.target.id] = stmt.annotation
        if fields:
            self._info.class_field_annotations[node.name] = fields


def _call_is_newtype(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "NewType"
    if isinstance(func, ast.Attribute):
        return func.attr == "NewType"
    return False


class NewTypeIndex:
    """Project-wide registry of NewType definitions and annotated symbols.

    Usage:

        index = NewTypeIndex()
        index.ingest(module_path, tree)
        ...
        index.finalise()
        # ... rules read from the finalised index ...
    """

    def __init__(self) -> None:
        self._modules: dict[str, _ModuleInfo] = {}
        self._newtype_bases: dict[NewTypeId, BuiltinBase] = {}
        self._finalised = False

    def _resolve_origin_module(self, dotted_name: str) -> str | None:
        """Map a dotted import name (e.g. 'pkg.models') to an ingested module path.

        Returns the unique ingested module whose path ends with `<dotted>.py`
        or `<dotted>/__init__.py` (with dots translated to path separators), so
        that names re-exported from a package's `__init__.py` resolve as well as
        those imported from a plain module. Returns None when there is no match
        or when multiple candidates exist (ambiguous import).
        """
        if dotted_name in self._modules:
            return dotted_name
        base = dotted_name.replace(".", "/")
        stems = (base + ".py", base + "/__init__.py")
        # `path == stem` covers a relative path that is exactly the module; otherwise a
        # separator must precede it, so that `mydb/models/common.py` is not mistaken for
        # `db.models.common` just because it ends with those characters. Without the
        # boundary such a module looks like a second candidate, the import reads as
        # ambiguous, and the index resolves nothing at all.
        matches = [path for path in self._modules if any(path == stem or path.endswith("/" + stem) for stem in stems)]
        if len(matches) == 1:
            return matches[0]
        return None

    def ingest(self, module_path: str, tree: ast.AST) -> None:
        """Record top-level definitions from one parsed module."""
        if self._finalised:
            msg = "Cannot ingest after finalise()"
            raise RuntimeError(msg)
        if not isinstance(tree, ast.Module):
            return
        info = _ModuleInfo(path=module_path)
        _ModuleIngestor(info).visit_Module(tree)
        self._modules[module_path] = info

    def finalise(self) -> None:
        """Resolve every NewType's base to a canonical BuiltinBase.

        Chains like `B = NewType("B", A)` where `A = NewType("A", str)` resolve
        through to STR. Unresolvable bases (custom classes, generics) become
        UNKNOWN so the rule simply skips them later.
        """
        if self._finalised:
            return
        for module_path, info in self._modules.items():
            for name in info.newtype_base_expr:
                identity = NewTypeId(module_path, name)
                self._newtype_bases[identity] = self._resolve_newtype_base(identity, set())
        self._finalised = True

    # ------------------------------------------------------------------
    # Lookup API consumed by rules
    # ------------------------------------------------------------------

    def resolve_local_name(self, module: str, name: str) -> NewTypeId | None:
        """Return the NewType identity for `name` as it appears in `module`.

        Handles three cases:
          * `name` is defined locally as a NewType in `module`.
          * `name` is imported — directly or via any number of re-exporting
            modules — from a tracked module that defines it as a NewType.
          * Anything else → None.
        """
        resolved = self._resolve_symbol(module, name, "newtype_base_expr")
        if resolved is None:
            return None
        defining_module, original_name = resolved
        return NewTypeId(defining_module, original_name)

    def resolve_annotation(self, module: str, expr: ast.expr) -> NewTypeId | None:
        """Return the NewType identity for an annotation expression.

        Only bare `Name` annotations are considered. Subscripted, attribute,
        callable, and string annotations all return None — the rule treats
        those as unresolved and stays silent.
        """
        if isinstance(expr, ast.Name):
            return self.resolve_local_name(module, expr.id)
        return None

    def lookup_class_field(self, class_module: str, class_name: str, field_name: str) -> NewTypeId | None:
        """Return the NewType identity of `ClassName.field` defined in `class_module`."""
        annotation = self.get_class_field_annotation(class_module, class_name, field_name)
        if annotation is None:
            return None
        return self.resolve_annotation(class_module, annotation)

    def lookup_function_return(self, module: str, function_name: str) -> NewTypeId | None:
        """Return the NewType identity of `function_name`'s return annotation."""
        annotation = self.get_function_return_annotation(module, function_name)
        if annotation is None:
            return None
        return self.resolve_annotation(module, annotation)

    def get_class_field_annotation(self, class_module: str, class_name: str, field_name: str) -> ast.expr | None:
        """Return the raw annotation expression of `ClassName.field` defined in `class_module`."""
        info = self._modules.get(class_module)
        if info is None:
            return None
        fields = info.class_field_annotations.get(class_name)
        if fields is None:
            return None
        return fields.get(field_name)

    def get_function_return_annotation(self, module: str, function_name: str) -> ast.expr | None:
        """Return the raw return-annotation expression of `function_name` in `module`."""
        info = self._modules.get(module)
        if info is None:
            return None
        return info.function_returns.get(function_name)

    def find_class_module(self, calling_module: str, class_name: str) -> tuple[str, str] | None:
        """Resolve `class_name` in `calling_module` to (defining_module, original_name).

        Handles `from x import Foo` and `from x import Foo as Bar` so the returned
        original_name is what the class is called in its defining module.
        """
        return self._resolve_symbol(calling_module, class_name, "class_field_annotations")

    def find_function_module(self, calling_module: str, function_name: str) -> tuple[str, str] | None:
        """Resolve `function_name` in `calling_module` to (defining_module, original_name)."""
        return self._resolve_symbol(calling_module, function_name, "function_returns")

    def is_newtype(self, identity: NewTypeId) -> bool:
        return identity in self._newtype_bases

    def canonical_base(self, identity: NewTypeId) -> BuiltinBase:
        return self._newtype_bases.get(identity, BuiltinBase.UNKNOWN)

    # ------------------------------------------------------------------
    # Internal resolution
    # ------------------------------------------------------------------

    def _resolve_newtype_base(self, identity: NewTypeId, visited: set[NewTypeId]) -> BuiltinBase:
        if identity in visited:
            return BuiltinBase.UNKNOWN
        visited.add(identity)
        info = self._modules.get(identity.module)
        expr = info.newtype_base_expr.get(identity.name) if info is not None else None
        if not isinstance(expr, ast.Name):
            # Non-trivial bases (subscripts, attributes, strings) are opaque to this index.
            return BuiltinBase.UNKNOWN
        if expr.id in _BUILTIN_BASE_NAMES:
            return _BUILTIN_BASE_NAMES[expr.id]
        next_id = self.resolve_local_name(identity.module, expr.id)
        if next_id is None:
            return BuiltinBase.UNKNOWN
        return self._resolve_newtype_base(next_id, visited)

    def _resolve_symbol(self, calling_module: str, name: str, attr: str) -> tuple[str, str] | None:
        """Locate `name` (as it appears in `calling_module`) in some module's `attr` mapping.

        `attr` is the _ModuleInfo dict to consult: one of "newtype_base_expr",
        "class_field_annotations", or "function_returns". Returns (defining_module,
        original_name) or None.

        Follows the alias chain as far as it goes, so a name reached through one or
        more re-exporting modules resolves to the same identity as one imported
        straight from the module that defines it. The walk stops at the first module
        that defines the name, at an untracked or external origin, or on revisiting a
        (module, name) pair — circular re-exports terminate rather than spin.
        """
        current_module: str = calling_module
        current_name: str = name
        visited: set[tuple[str, str]] = set()
        while (current_module, current_name) not in visited:
            visited.add((current_module, current_name))
            info = self._modules.get(current_module)
            if info is None:
                return None
            if current_name in getattr(info, attr):
                return (current_module, current_name)
            alias = info.aliases.get(current_name)
            if alias is None or alias[0] == "<external>":
                return None
            origin_dotted, original_name = alias
            origin_module = self._resolve_origin_module(origin_dotted)
            if origin_module is None:
                return None
            current_module = origin_module
            current_name = original_name
        return None
