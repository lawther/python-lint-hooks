"""Single-walk AST runner that dispatches to all enabled rules."""

from __future__ import annotations

import ast
import tokenize
from typing import TYPE_CHECKING

from ml_lints.analyzers.newtype_index import NewTypeIndex
from ml_lints.comments import scan_comments
from ml_lints.rules import CheckContext, Rule, all_rules
from ml_lints.violation import RuleCode, Violation

if TYPE_CHECKING:
    from pathlib import Path


def check_file(
    path: Path,
    enabled_codes: frozenset[RuleCode] | None = None,
    project_index: NewTypeIndex | None = None,
) -> list[Violation]:
    """Parse path and return violations from all enabled rules.

    When enabled_codes is None every registered rule runs. The CLI computes the enabled
    set from --select / --ignore and passes it in so disabled rules are never instantiated.

    project_index is an optional pre-built cross-file index. Rules that need cross-module
    type resolution (ML108, ML109) consume it; without one, they stay silent.

    Reads via `tokenize.open`, which honours a PEP 263 encoding declaration (or a UTF-8
    BOM) instead of assuming UTF-8, so correctly-declared non-UTF-8 source is read as
    Python itself would read it. Raises OSError, SyntaxError (a malformed encoding
    declaration, or a genuine syntax error) or UnicodeDecodeError if the file still
    cannot be read or parsed; `check_paths` is responsible for catching these and
    reporting the skip as an ML000 violation instead of letting the run abort.
    """
    with tokenize.open(path) as f:
        source = f.read()
        encoding = f.encoding
    source_lines = tuple(source.splitlines())
    tree = ast.parse(source, filename=str(path))
    context = CheckContext(
        path,
        source_lines,
        project_index=project_index,
        encoding=encoding,
        comments=scan_comments(source),
    )

    rules: list[Rule] = [cls(context) for cls in all_rules() if enabled_codes is None or cls.code in enabled_codes]

    if rules:
        _walk(tree, rules)

    return [v for rule in rules for v in rule.violations]


def check_paths(
    paths: list[Path],
    enabled_codes: frozenset[RuleCode] | dict[Path, frozenset[RuleCode]] | None = None,
) -> list[Violation]:
    """Check multiple files with a shared project-wide NewType index.

    Performs a pre-pass to build a cross-file index of NewType definitions, class
    field annotations, and function return annotations. Then runs the per-file
    rule pass with that index available in CheckContext.

    Files that fail to read or parse during the pre-pass are silently skipped from the
    index; the per-file pass below reports each one once, as an ML000 violation,
    instead of letting the failure abort the whole run.
    """
    index = NewTypeIndex()
    for path in paths:
        try:
            with tokenize.open(path) as f:
                source = f.read()
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        index.ingest(str(path.resolve()), tree)
    index.finalise()

    violations: list[Violation] = []
    for path in paths:
        codes = _resolve_codes(enabled_codes, path)
        try:
            violations.extend(check_file(path, codes, project_index=index))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            if codes is None or RuleCode.ML000 in codes:
                violations.append(
                    Violation(
                        code=RuleCode.ML000,
                        message=f"could not read or parse this file ({type(exc).__name__}): {exc}",
                        path=path,
                        line=1,
                        col=1,
                    )
                )
    return violations


def _resolve_codes(
    enabled_codes: frozenset[RuleCode] | dict[Path, frozenset[RuleCode]] | None,
    path: Path,
) -> frozenset[RuleCode] | None:
    if isinstance(enabled_codes, dict):
        return enabled_codes.get(path)
    if isinstance(enabled_codes, frozenset):
        return enabled_codes
    return None


def _walk(node: ast.AST, rules: list[Rule]) -> None:
    """Recursively walk the AST, dispatching enter/leave hooks to every rule."""
    node_type = type(node).__name__
    enter_attr = f"enter_{node_type}"
    leave_attr = f"leave_{node_type}"

    for rule in rules:
        method = getattr(rule, enter_attr, None)
        if method is not None:
            method(node)

    for child in ast.iter_child_nodes(node):
        _walk(child, rules)

    for rule in rules:
        method = getattr(rule, leave_attr, None)
        if method is not None:
            method(node)
