# Contributing a New Rule

This guide is the contract for adding lint rules to this project. It is written for human developers and AI agents alike. Follow it precisely.

## Quick start

```sh
just new-rule ML150
```

This creates two files pre-filled with the right structure:

- `src/python_lint_hooks/rules/ml150.py` — the rule implementation
- `tests/rules/test_ml150.py` — the test file

Edit both, then run:

```sh
just precommit   # lint, type-check, tests, README update
```

---

## Rule code ranges

| Range | Category | Enum value |
|-------|----------|------------|
| ML1xx | Return type / signature shape | `RuleCategory.RETURN_TYPES` |
| ML1xx | Parameter type shape | `RuleCategory.PARAMETER_TYPES` |
| ML1xx | Type hygiene (NewType casts) | `RuleCategory.TYPE_HYGIENE` |
| ML2xx | Class / dataclass shape | `RuleCategory.CLASS_SHAPE` |
| ML3xx | Scope violations | `RuleCategory.SCOPE` |
| ML4xx | Data trust / external data | `RuleCategory.DATA_TRUST` |
| ML5xx | Localisation / Spelling | `RuleCategory.LOCALISATION` |
| ML6xx | Testing pitfalls | `RuleCategory.TESTING` |

Pick the next unused code in the appropriate range.

---

## The rule contract

Every rule file must:

1. Live at `src/python_lint_hooks/rules/<code>.py` (e.g. `ml150.py`).
2. Define exactly one class decorated with `@register`.
3. Provide a clear rationale in the class docstring. This is used for documentation and CLI help.
4. Declare these four mandatory metadata fields and two example fields:

```python
code: ClassVar[RuleCode] = RuleCode.ML150
category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
summary: ClassVar[str] = "One-line description for the README table"
suggestion: ClassVar[str] = "What the author should do instead"

# Must trigger at least one violation of this rule
bad_example: ClassVar[str] = \"\"\"
def get_data() -> dict: ...
\"\"\"

# Must trigger zero violations of ANY rule
good_examples: ClassVar[list[str]] = [
    \"\"\"
@dataclass(frozen=True)
class Data: ...
\"\"\"
]
```

5. Emit violations **only** via `self.report()` — never by appending to `self.violations` directly.
5. **Not recurse** inside hook methods — the runner handles tree traversal.

`just new-rule` handles adding `RuleCode.ML150` to the enum in `violation.py` automatically. The file is auto-discovered at import time via `pkgutil.iter_modules`.

---

## Hook methods

Rules use `enter_<NodeType>` / `leave_<NodeType>` hooks, **not** `ast.NodeVisitor.visit_*`. The runner calls these as it walks the AST once.

```python
def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
    # called when the walker enters a FunctionDef
    # inspect node here; call self.report() if violated
    # do NOT recurse — no self.generic_visit(), no ast.walk()

def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
    # called after all children of node have been visited
    # use this for state cleanup (e.g. decrementing a depth counter)
```

`enter_*` and `leave_*` are symmetric. Use `leave_*` whenever you need to clean up state pushed in `enter_*`.

### Async functions

Async functions are a separate node type (`ast.AsyncFunctionDef`). If your rule applies to both, alias the hook methods:

```python
enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]
```

---

## Tracking function nesting depth

Some rules only apply to top-level functions (e.g. return-type rules ignore inner/nested functions). Track depth yourself — the base class does not do it automatically:

```python
def __init__(self, context: CheckContext) -> None:
    super().__init__(context)
    self._function_depth: int = 0

def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
    if self._function_depth == 0:
        # only fires for top-level functions
        ...
    self._function_depth += 1

def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
    self._function_depth -= 1

enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]
```

---

## Emitting violations

Call `self.report()` — it handles noqa suppression automatically:

```python
self.report(
    node.lineno,
    node.col_offset + 1,
    f"Function '{node.name}' does something bad",
)
```

For multi-line annotations where the `# noqa` comment may appear on a different line than the violation, pass explicit `noqa_lines`:

```python
self.report(
    finding.line,
    finding.col,
    message,
    noqa_lines=list(range(annotation_start, annotation_end + 1)),
)
```

**Never** call `has_noqa()` directly — use `self.report()`.

---

## Using the shared type analyzer

For any rule that needs to determine whether a type annotation is "forbidden" (bare dict, bare tuple, dict of primitives, etc.), use `ForbiddenTypeAnalyzer` from `python_lint_hooks.analyzers.forbidden_types`. Do not re-implement the analysis.

```python
from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer

analyzer = ForbiddenTypeAnalyzer()
analyzer.analyze(node)          # node is an ast.expr (e.g. a return annotation)
findings = analyzer.findings    # list[ForbiddenTypeFinding]
```

Each `ForbiddenTypeFinding` has `.code` (e.g. `"ML102"`), `.line`, and `.col`. Consumers use it in two ways:

- **ML100-104**: filter findings by `.code == self.code` and report each one.
- **ML105, ML201**: use `bool(analyzer.findings)` as a yes/no signal that the annotation is forbidden.

---

## Testing requirements

Every rule needs a test file at `tests/rules/test_<code>.py` with at minimum:

| Test | What it checks |
|------|----------------|
| Positive | A snippet that **should** trigger the rule |
| Negative | A valid snippet that **must not** be flagged |
| noqa suppression | The rule is silenced by `# noqa: <CODE>` |

Use the shared helpers from `tests/conftest.py`:

```python
from tests.conftest import check, codes

def test_something_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> dict: ...\n", tmp_path)
    assert codes(violations) == ["ML100"]
```

`check(code, tmp_path)` writes the snippet to a temp file and runs the full runner against it (all registered rules). Assert on the specific codes you expect — do not assume other rules are silent.

---

## README table

The rules table in `README.md` is generated automatically from the `summary` and `suggestion` fields on each rule class. It is regenerated during `just precommit` (auto-staged). You can also regenerate manually:

```sh
just docs-rules
```

Do not edit the table by hand — your changes will be overwritten.

---

## Complete example

A minimal rule that flags functions returning `list` at the top level:

```python
"""ML150 — function returns a bare list.

`list` with no type parameter gives callers no information about element type.
Use a typed list[T] or a custom collection instead.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML150(Rule):
    code: ClassVar[RuleCode] = RuleCode.ML150
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a bare `list`"
    suggestion: ClassVar[str] = "Use `list[T]` with an explicit element type"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._function_depth == 0 and node.returns is not None:
            if isinstance(node.returns, ast.Name) and node.returns.id == "list":
                self.report(
                    node.returns.lineno,
                    node.returns.col_offset + 1,
                    f"Function '{node.name}' returns bare list; use list[T] instead",
                )
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]
```
