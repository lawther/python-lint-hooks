"""ForbiddenTypeAnalyzer — pure analysis of type annotations for disallowed shapes.

Consumers use findings differently:
- ML100-104: each rule reports findings matching its own code.
- ML105, ML201: use `bool(findings)` as a yes/no signal that an annotation is forbidden.
- ML110: filters for ML104 findings in parameter annotations.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from python_lint_hooks.violation import RuleCode

_DICT_NAMES: frozenset[str] = frozenset({"dict", "Dict"})
_MAPPING_NAMES: frozenset[str] = frozenset({"Mapping", "MutableMapping"})
_TUPLE_NAMES: frozenset[str] = frozenset({"tuple", "Tuple"})
_PRIMITIVE_NAMES: frozenset[str] = frozenset({"str", "int", "float", "bool", "bytes", "Any", "None"})
_KEY_VALUE_SUBSCRIPT_LEN = 2  # dict[K, V] / Mapping[K, V] subscript is always a 2-tuple


@dataclass(frozen=True)
class ForbiddenTypeFinding:
    """A single forbidden-type finding in a type annotation (no path/message — pure analysis)."""

    code: RuleCode
    line: int
    col: int


class ForbiddenTypeAnalyzer:
    """Recursively inspect a type annotation AST node and collect forbidden-type findings.

    Instantiate once per annotation, call `analyze(node)`, then read `.findings`.
    The analyzer does NOT emit Violations — that is the caller's responsibility.
    """

    def __init__(self) -> None:
        self.findings: list[ForbiddenTypeFinding] = []

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
        elif isinstance(node, ast.Tuple):
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML101, node.lineno, node.col_offset + 1))
            for elt in node.elts:
                self.analyze(elt)

    def _check_name(self, node: ast.Name) -> None:
        if node.id in _DICT_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML100, node.lineno, node.col_offset + 1))
        elif node.id in _MAPPING_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML106, node.lineno, node.col_offset + 1))
        elif node.id in _TUPLE_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML101, node.lineno, node.col_offset + 1))

    def _check_attribute(self, node: ast.Attribute) -> None:
        if node.attr in _DICT_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML100, node.lineno, node.col_offset + 1))
        elif node.attr in _MAPPING_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML106, node.lineno, node.col_offset + 1))
        elif node.attr in _TUPLE_NAMES:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML101, node.lineno, node.col_offset + 1))

    def _check_subscript(self, node: ast.Subscript) -> None:
        head = node.value
        head_name = ""
        if isinstance(head, ast.Name):
            head_name = head.id
        elif isinstance(head, ast.Attribute):
            head_name = head.attr

        if head_name in _DICT_NAMES:
            self._check_dict_subscript(node)
        elif head_name in _MAPPING_NAMES:
            self._check_mapping_subscript(node)
        elif head_name in _TUPLE_NAMES:
            self._check_tuple_subscript(node)
        elif isinstance(node.slice, ast.Tuple):
            for elt in node.slice.elts:
                self.analyze(elt)
        else:
            self.analyze(node.slice)

    def _check_dict_subscript(self, node: ast.Subscript) -> None:
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != _KEY_VALUE_SUBSCRIPT_LEN:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML100, node.lineno, node.col_offset + 1))
            return

        k, v = node.slice.elts
        if _is_primitive(k) and _is_primitive(v):
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML102, node.lineno, node.col_offset + 1))

        self.analyze(k)
        self.analyze(v)

    def _check_mapping_subscript(self, node: ast.Subscript) -> None:
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != _KEY_VALUE_SUBSCRIPT_LEN:
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML106, node.lineno, node.col_offset + 1))
            return

        k, v = node.slice.elts
        if _is_primitive(k) and _is_primitive(v):
            self.findings.append(ForbiddenTypeFinding(RuleCode.ML107, node.lineno, node.col_offset + 1))

        self.analyze(k)
        self.analyze(v)

    def _check_tuple_subscript(self, node: ast.Subscript) -> None:
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        is_variable = any(isinstance(elt, ast.Constant) and elt.value is Ellipsis for elt in elts)

        code = RuleCode.ML104 if is_variable else RuleCode.ML103
        self.findings.append(ForbiddenTypeFinding(code, node.lineno, node.col_offset + 1))

        for elt in elts:
            if not (isinstance(elt, ast.Constant) and elt.value is Ellipsis):
                self.analyze(elt)


def _is_primitive(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _PRIMITIVE_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _PRIMITIVE_NAMES
    if isinstance(node, ast.Constant):
        return node.value is None or node.value is Ellipsis
    return False
