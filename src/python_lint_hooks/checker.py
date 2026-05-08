"""AST-based checks for return types, classes, dataclasses, and unvalidated external data."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

from python_lint_hooks.noqa import has_noqa as _has_noqa
from python_lint_hooks.violation import Violation

_DICT_NAMES: frozenset[str] = frozenset({"dict", "Dict"})
_TUPLE_NAMES: frozenset[str] = frozenset({"tuple", "Tuple"})
_PRIMITIVE_NAMES: frozenset[str] = frozenset({"str", "int", "float", "bool", "bytes", "Any", "None"})
_UNTRUSTED_FUNCS: frozenset[str] = frozenset({"loads", "load", "safe_load", "full_load", "literal_eval"})

_FuncNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef


__all__ = ["Violation", "check_file"]


class _ReturnAnalyzer:
    """Recursive analyzer for function return type annotations."""

    def __init__(self, func_name: str) -> None:
        self.func_name = func_name
        self.violations: list[tuple[str, str, int, int]] = []

    def analyze(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            self._check_name(node)
        elif isinstance(node, ast.Attribute):
            self._check_attribute(node)
        elif isinstance(node, ast.Subscript):
            self._check_subscript(node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            self.analyze(node.left)
            self.analyze(node.right)
        elif isinstance(node, ast.Tuple):  # e.g. -> (int, str) which is valid but we treat as tuple
            self.violations.append(
                (
                    "ML101",
                    f"Function '{self.func_name}' returns bare tuple; use a NamedTuple instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )
            for elt in node.elts:
                self.analyze(elt)

    def _check_name(self, node: ast.Name) -> None:
        if node.id in _DICT_NAMES:
            self.violations.append(
                (
                    "ML100",
                    f"Function '{self.func_name}' returns bare dict; use a dataclass instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )
        elif node.id in _TUPLE_NAMES:
            self.violations.append(
                (
                    "ML101",
                    f"Function '{self.func_name}' returns bare tuple; use a NamedTuple instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )

    def _check_attribute(self, node: ast.Attribute) -> None:
        if node.attr in _DICT_NAMES:
            self.violations.append(
                (
                    "ML100",
                    f"Function '{self.func_name}' returns bare dict; use a dataclass instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )
        elif node.attr in _TUPLE_NAMES:
            self.violations.append(
                (
                    "ML101",
                    f"Function '{self.func_name}' returns bare tuple; use a NamedTuple instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )

    def _check_subscript(self, node: ast.Subscript) -> None:
        # Resolve head (e.g. dict in dict[str, str])
        head = node.value
        head_name = ""
        if isinstance(head, ast.Name):
            head_name = head.id
        elif isinstance(head, ast.Attribute):
            head_name = head.attr

        if head_name in _DICT_NAMES:
            self._analyze_dict_subscript(node)
        elif head_name in _TUPLE_NAMES:
            self._analyze_tuple_subscript(node)
        # It's something else like list[...] or Optional[...], recurse into slice
        elif isinstance(node.slice, ast.Tuple):
            for elt in node.slice.elts:
                self.analyze(elt)
        else:
            self.analyze(node.slice)

    def _analyze_dict_subscript(self, node: ast.Subscript) -> None:
        # dict[K, V]
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:  # noqa: PLR2004
            # dict with one arg (like dict[str]) is technically invalid but we catch as bare
            self.violations.append(
                (
                    "ML100",
                    f"Function '{self.func_name}' returns bare dict; use a dataclass instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )
            return

        k, v = node.slice.elts
        if self._is_primitive(k) and self._is_primitive(v):
            message = (
                f"Function '{self.func_name}' returns dict of primitives; "
                "use NewType for keys/values or use a dataclass"
            )
            self.violations.append(("ML102", message, node.lineno, node.col_offset + 1))

        # Still recurse into K and V in case they contain further violations (e.g. dict[str, list[dict]])
        self.analyze(k)
        self.analyze(v)

    def _analyze_tuple_subscript(self, node: ast.Subscript) -> None:
        # tuple[T, ...] or tuple[T1, T2]
        is_variable = False
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]

        if any(isinstance(elt, ast.Constant) and elt.value is Ellipsis for elt in elts):
            is_variable = True

        if is_variable:
            message = (
                f"Function '{self.func_name}' returns variable-length tuple; use list[T] or custom collection instead"
            )
            self.violations.append(("ML104", message, node.lineno, node.col_offset + 1))
        else:
            self.violations.append(
                (
                    "ML103",
                    f"Function '{self.func_name}' returns fixed-length tuple; use a NamedTuple instead",
                    node.lineno,
                    node.col_offset + 1,
                )
            )

        for elt in elts:
            if not (isinstance(elt, ast.Constant) and elt.value is Ellipsis):
                self.analyze(elt)

    def _is_primitive(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in _PRIMITIVE_NAMES
        if isinstance(node, ast.Attribute):
            return node.attr in _PRIMITIVE_NAMES
        if isinstance(node, ast.Constant):
            return node.value is None or node.value is Ellipsis
        return False


@dataclass(frozen=True)
class TaintInfo:
    is_tainted: bool
    source_node: ast.AST | None = None


class _Checker(ast.NodeVisitor):
    def __init__(self, path: Path, source_lines: list[str]) -> None:
        self._path = path
        self._source_lines = source_lines
        self._function_depth = 0
        self.violations: list[Violation] = []
        self._taint_stack: list[dict[str, TaintInfo]] = [{}]
        self._flagged_sources: set[ast.AST] = set()

    def _is_tainted(self, name: str) -> bool:
        """Check if a name is tainted in the current scope or any parent scope."""
        for scope in reversed(self._taint_stack):
            if name in scope:
                return scope[name].is_tainted
        return False

    def _get_taint_info(self, name: str) -> TaintInfo:
        for scope in reversed(self._taint_stack):
            if name in scope:
                return scope[name]
        return TaintInfo(False)

    def _set_taint(self, name: str, is_tainted: bool, source_node: ast.AST | None = None) -> None:
        """Set the taint status for a name in the current (topmost) scope."""
        self._taint_stack[-1][name] = TaintInfo(is_tainted, source_node)

    def _is_untrusted_source(self, node: ast.AST | None) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and (func.attr in _UNTRUSTED_FUNCS or func.attr == "json"):
            return True
        return bool(isinstance(func, ast.Name) and func.id in _UNTRUSTED_FUNCS)

    def _get_names(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            names = []
            for elt in node.elts:
                names.extend(self._get_names(elt))
            return names
        return []

    def _report_ml400(self, name: str, usage_node: ast.AST) -> None:
        info = self._get_taint_info(name)
        if not info.is_tainted:
            return

        # If we have a source node, flag that. Otherwise flag the usage site.
        report_node = info.source_node if info.source_node else usage_node
        if report_node in self._flagged_sources:
            return

        # Type safety: most nodes have lineno/col_offset but ast.AST doesn't guarantee it
        if not hasattr(usage_node, "lineno") or not hasattr(report_node, "lineno"):
            return

        usage_lineno = cast(int, usage_node.lineno)
        report_lineno = cast(int, report_node.lineno)
        report_col = cast(int, getattr(report_node, "col_offset", 0))

        if not _has_noqa(self._source_lines, [usage_lineno], "ML400") and not _has_noqa(
            self._source_lines, [report_lineno], "ML400"
        ):
            self._flagged_sources.add(report_node)
            msg = f"Untrusted data in '{name}' used without Pydantic validation"
            if info.source_node:
                msg = f"Variable '{name}' assigned unvalidated data and used here; validate with Pydantic"

            self.violations.append(
                Violation(
                    code="ML400",
                    message=msg,
                    path=self._path,
                    line=report_lineno,
                    col=report_col + 1,
                )
            )

    def _visit_function(self, node: _FuncNode) -> None:
        self._taint_stack.append({})
        if self._function_depth == 0 and node.returns is not None:
            analyzer = _ReturnAnalyzer(node.name)
            analyzer.analyze(node.returns)

            for code, message, line, col in analyzer.violations:
                noqa_lines = [line]
                # If it's a multi-line return annotation, check all relevant lines
                if node.returns.end_lineno is not None and node.returns.end_lineno != line:
                    noqa_lines.extend(range(line, node.returns.end_lineno + 1))

                if not _has_noqa(self._source_lines, noqa_lines, code):
                    self.violations.append(
                        Violation(
                            code=code,
                            message=message,
                            path=self._path,
                            line=line,
                            col=col,
                        )
                    )

        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1
        self._taint_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        is_untrusted = self._is_untrusted_source(node.value)
        source_node = node if is_untrusted else None

        # If the value is a name, inherit its source node
        if not is_untrusted and isinstance(node.value, ast.Name):
            info = self._get_taint_info(node.value.id)
            if info.is_tainted:
                is_untrusted = True
                source_node = info.source_node

        for target in node.targets:
            for name in self._get_names(target):
                self._set_taint(name, is_untrusted, source_node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            is_untrusted = self._is_untrusted_source(node.value)
            source_node = node if is_untrusted else None

            if not is_untrusted and isinstance(node.value, ast.Name):
                info = self._get_taint_info(node.value.id)
                if info.is_tainted:
                    is_untrusted = True
                    source_node = info.source_node

            for name in self._get_names(node.target):
                self._set_taint(name, is_untrusted, source_node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        is_tainted = self._is_untrusted_source(node.iter)
        source_node = node if is_tainted else None

        if not is_tainted and isinstance(node.iter, ast.Name):
            info = self._get_taint_info(node.iter.id)
            if info.is_tainted:
                is_tainted = True
                source_node = info.source_node

        if is_tainted:
            for name in self._get_names(node.target):
                self._set_taint(name, True, source_node)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def _handle_comprehension(self, generators: list[ast.comprehension]) -> None:
        for gen in generators:
            is_tainted = self._is_untrusted_source(gen.iter)
            source_node = gen if is_tainted else None

            if not is_tainted and isinstance(gen.iter, ast.Name):
                info = self._get_taint_info(gen.iter.id)
                if info.is_tainted:
                    is_tainted = True
                    source_node = info.source_node

            if is_tainted:
                for name in self._get_names(gen.target):
                    self._set_taint(name, True, source_node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name):
            self._report_ml400(node.value.id, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # ML400: Untrusted data accessed via .get()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and isinstance(node.func.value, ast.Name):
            self._report_ml400(node.func.value.id, node)
        # GEMINI.md: "I want to add a rule that will catch a sneaky attempt like this where they try to define a NewType
        # that would fail one of the existing lint checks."
        # ML105: NewType wrapping forbidden types
        if self._is_newtype_call(node) and len(node.args) >= 2:  # noqa: PLR2004
            analyzer = _ReturnAnalyzer("dummy")
            analyzer.analyze(node.args[1])
            if analyzer.violations:
                # Get the name from the first argument if it's a constant string
                newtype_name = "unknown"
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    newtype_name = node.args[0].value

                if not _has_noqa(self._source_lines, [node.lineno], "ML105"):
                    msg = f"NewType '{newtype_name}' wraps a forbidden type; use a dataclass or NamedTuple instead"
                    self.violations.append(
                        Violation(
                            code="ML105",
                            message=msg,
                            path=self._path,
                            line=node.lineno,
                            col=node.col_offset + 1,
                        )
                    )

        self.generic_visit(node)

    def _is_newtype_call(self, node: ast.Call) -> bool:
        func = node.func
        return (isinstance(func, ast.Name) and func.id == "NewType") or (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "typing"
            and func.attr == "NewType"
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._function_depth > 0 and not _has_noqa(self._source_lines, [node.lineno], "ML300"):
            self.violations.append(
                Violation(
                    code="ML300",
                    message=f"Class '{node.name}' defined inside a function",
                    path=self._path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                )
            )

        # GEMINI.md: "Strongly prefer to make dataclasses immutable where possible. Use @dataclass(frozen=True)"
        self._check_frozen_dataclass(node)
        self._check_wrapper_class(node)
        self.generic_visit(node)

    def _check_wrapper_class(self, node: ast.ClassDef) -> None:
        # ML201: Classes wrapping only forbidden types
        # We only care about annotated assignments (AnnAssign) in the class body.
        # If there are no AnnAssigns, it's not a data-carrying class we want to flag here.
        annotations = [stmt for stmt in node.body if isinstance(stmt, ast.AnnAssign)]
        if not annotations:
            return

        all_forbidden = True
        for ann in annotations:
            if ann.annotation is None:
                continue
            analyzer = _ReturnAnalyzer("dummy")
            analyzer.analyze(ann.annotation)
            if not analyzer.violations:
                all_forbidden = False
                break

        if all_forbidden and not _has_noqa(self._source_lines, [node.lineno], "ML201"):
            self.violations.append(
                Violation(
                    code="ML201",
                    message=f"Class '{node.name}' only contains forbidden types; use a proper abstraction",
                    path=self._path,
                    line=node.lineno,
                    col=node.col_offset + 1,
                )
            )

    def _check_frozen_dataclass(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            # Handle both @dataclass and @dataclasses.dataclass
            is_dataclass = False
            if (isinstance(decorator, ast.Name) and decorator.id == "dataclass") or (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "dataclasses"
                and decorator.attr == "dataclass"
            ):
                is_dataclass = True
            elif isinstance(decorator, ast.Call):
                func = decorator.func
                if (isinstance(func, ast.Name) and func.id == "dataclass") or (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "dataclasses"
                    and func.attr == "dataclass"
                ):
                    is_dataclass = True

            if is_dataclass:
                is_frozen = False
                if isinstance(decorator, ast.Call):
                    for keyword in decorator.keywords:
                        if (
                            keyword.arg == "frozen"
                            and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is True
                        ):
                            is_frozen = True
                            break

                if not is_frozen and not _has_noqa(self._source_lines, [decorator.lineno], "ML200"):
                    self.violations.append(
                        Violation(
                            code="ML200",
                            message=f"Dataclass '{node.name}' is not frozen; use @dataclass(frozen=True)",
                            path=self._path,
                            line=decorator.lineno,
                            col=decorator.col_offset + 1,
                        )
                    )
                break


def check_file(path: Path) -> list[Violation]:
    """Parse path and return all ML rule violations found."""
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    checker = _Checker(path, source_lines)
    checker.visit(tree)
    return checker.violations
