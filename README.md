# ml-lints

Custom Python linting rules, distributed as a pip-installable CLI tool.

These rules are aimed at optimising AI agent development. A common failure mode of Python projects as they get larger is 'wtf is this tuple?', 'what's this string/int?'. By forcing a more self-documenting code style during development, agents will spend fewer tokens parsing and analysing the code everytime you spin up a fresh context.

## Rules

<!-- rules-table-start -->
| Code | Description | Suggestion |
|------|-------------|------------|
| [`ML100`](docs/rules/ML100.md) | Function returns a bare `dict` | Use a dataclass instead |
| [`ML101`](docs/rules/ML101.md) | Function returns a bare `tuple` | Use a NamedTuple instead |
| [`ML102`](docs/rules/ML102.md) | Function returns a `dict` of primitives | Use a dataclass or `NewType` for keys/values |
| [`ML103`](docs/rules/ML103.md) | Function returns a fixed-length `tuple` | Use a NamedTuple instead |
| [`ML104`](docs/rules/ML104.md) | Function returns a variable-length `tuple` | Use `list[T]` or a custom collection instead |
| [`ML105`](docs/rules/ML105.md) | `NewType` wraps a forbidden type | Use a dataclass or NamedTuple instead |
| [`ML106`](docs/rules/ML106.md) | Function returns a bare `Mapping` | Use a dataclass instead |
| [`ML107`](docs/rules/ML107.md) | Function returns a `Mapping` of primitives | Use a dataclass or `NewType` for keys/values |
| [`ML108`](docs/rules/ML108.md) | No-op `NewType` cast (value already of that type) | Drop the redundant cast |
| [`ML109`](docs/rules/ML109.md) | Cast between two `NewType`s of the same base | Unify the two NewTypes — they model the same concept |
| [`ML110`](docs/rules/ML110.md) | Function parameter has variable-length `tuple` annotation | Use `list[T]`, `Sequence[T]`, or a NamedTuple instead |
| [`ML200`](docs/rules/ML200.md) | Dataclass is not frozen | Use `@dataclass(frozen=True)` |
| [`ML201`](docs/rules/ML201.md) | Class contains only forbidden types | Use a proper abstraction with well-typed fields |
| [`ML202`](docs/rules/ML202.md) | Constructor called by spreading `.__dict__` or `vars()` | Use `dataclasses.replace(obj, field=value)` instead |
| [`ML300`](docs/rules/ML300.md) | Class defined inside a function | Move it to module level |
| [`ML400`](docs/rules/ML400.md) | Unvalidated external data used without Pydantic validation | Validate with a Pydantic model before use |
| [`ML500`](docs/rules/ML500.md) | American English spelling detected | Use Australian English spelling instead |
| [`ML501`](docs/rules/ML501.md) | Hacky pluralisation in string literal | Avoid hacky parenthetical or bracketed plurals like '(s)'. Use proper pluralisation or rephrase the sentence. Remember to also check and update verb agreements (e.g. 'is/are', 'need/needs', 'has/have') in surrounding text. |
| [`ML600`](docs/rules/ML600.md) | `@patch(new=Mock(...))` shares one mock instance across tests | Use `new_callable=Mock` (or `MagicMock`/`AsyncMock`) instead |
<!-- rules-table-end -->

**ML100 - ML107** catch violations related to return types. Unlike standard linting, these rules are **recursive** and will catch bare or primitive dicts/tuples even when nested inside other types like `list[...]` or `Optional[...]`.

**The `NewType` Exception:** `ML102` and `ML107` only flag dictionaries/mappings where both the key and value are standard Python primitives (`str`, `int`, `float`, etc.). If you use a custom type (e.g. via `NewType`), the dictionary/mapping is permitted as a valid mapping.

Functions defined inside other functions are exempt from ML100-ML107 — inner definitions are implementation details and are not part of a public interface.

**ML500** checks identifiers, function and class names, argument names, comments, and docstrings for American English spelling. Several categories are automatically exempt to avoid false positives with external APIs and third-party libraries:

- **Imported names** — names brought in via `import` or `from … import` are never flagged at the usage site. The correct place to flag a misspelling is the definition; fixing it there cascades to all usages via normal refactoring. This means using a third-party class like `HTTPAuthorizationCredentials` in a type annotation will not trigger ML500.
- **Attribute access** — `obj.color` is ignored in code; you do not control the attribute name.
- **Inline dotted names in text** — any `name.attr` token in a comment or docstring (e.g. `colors.get`, `api.get_color`) is ignored in its entirety; both sides of the dot are external API names the developer cannot rename.
- **Keyword arguments** — `func(color="red")` is ignored; you do not control the parameter name.
- **Non-docstring string literals** — `"color"` is ignored to avoid false positives with JSON keys, API payloads, and similar.
- **URLs** — anything following `http://` or `https://` is ignored; URL path segments are outside the developer's control.


## Installation

Add as a dev dependency using a git source. Pin to a specific tag for reproducibility:

```toml
# pyproject.toml
[dependency-groups]
dev = [
    "ml-lints",
    # ... other dev deps
]

```

During local development of the hook itself, use a path source instead:

```toml
[tool.uv.sources]
ml-lints = { path = "../python-lint-hooks", editable = true }
```

Then run:

```sh
uv sync
```

## Usage

```sh
# Check a directory
uv run ml-lints src/

# Check specific files
uv run ml-lints src/mypackage/utils.py

# Check multiple directories
uv run ml-lints src/ lib/

# Use a non-default config file
uv run ml-lints src/ --config path/to/pyproject.toml

# Exclusion overrides (Ruff-style; comma-separated, repeatable)
uv run ml-lints src/ --exclude venv/,node_modules/
uv run ml-lints src/ --extend-exclude build/
uv run ml-lints src/ --no-respect-gitignore
uv run ml-lints src/ --force-exclude

# Rule selection and ignoring (comma-separated, repeatable)
uv run ml-lints src/ --select ML100,ML200
uv run ml-lints src/ --extend-select ML300
uv run ml-lints src/ --ignore ML101
uv run ml-lints src/ --extend-ignore ML100
```

Note: paths must precede these options on the command line (as in the examples above) — argparse cannot otherwise tell a path apart from another value for a repeatable option.

Exits with code `1` if any violations are found, `0` otherwise. Output follows the ruff/flake8 format:

```
src/mypackage/utils.py:42:1: ML100 Function 'parse_response' returns bare dict; use a dataclass instead
src/mypackage/models.py:17:5: ML103 Function 'as_pair' returns fixed-length tuple; use a NamedTuple instead
src/mypackage/models.py:10:1: ML200 Dataclass 'Config' is not frozen; use @dataclass(frozen=True)
```

## Configuration

Configure in `pyproject.toml` under `[tool.ml-lints]`. Options behave similarly to [Ruff's selection settings](https://docs.astral.sh/ruff/settings/#select) and [exclusion settings](https://docs.astral.sh/ruff/settings/#exclude).

```toml
[tool.ml-lints]
# Rule selection (prefix matching supported, e.g. "ML")
select = ["ML"]
extend-select = []
ignore = []
extend-ignore = []

# Exclusions
# Overwrites the default exclusion list
exclude = ["tests/", "migrations/"]

# Adds to the exclusion list without overwriting defaults
extend-exclude = ["scripts/"]

# Respect .gitignore files (default: true)
respect-gitignore = true

# Enforce exclusions even for paths passed explicitly on command line (default: false)
force-exclude = false
```

### Rule Selection Behavior
*   **`select`**: Resets the active rules. CLI `--select` completely overrides the configuration `select`.
*   **`ignore`**: Disables specific rules. CLI `--ignore` completely overrides the configuration `ignore`.
*   **`extend-*`**: These flags are additive across both CLI and configuration.
*   **Prefix Matching**: You can select or ignore entire categories using prefixes. For example, `select = ["ML"]` enables all rules starting with `ML`.
*   **Precedence**: `ignore` always takes precedence over `select`. If a rule is both selected and ignored, it will be ignored.

### Default Exclusions
By default, `ml-lints` excludes a comprehensive list of common "junk" and environment directories, including `.git`, `.venv`, `node_modules`, `__pycache__`, `build`, `dist`, etc.

## Suppressing individual violations

Place a `# noqa: <code>` comment on the `def` line (or on the return annotation line for multi-line signatures):

```python
# Suppress a specific code
def legacy_helper() -> dict[str, str]:  # noqa: ML102
    ...

# Suppress on the annotation line for multi-line signatures
def build_index(
    items: list[str],
) -> dict[str, int]:  # noqa: ML102
    ...
```

For **ML500 docstring violations**, place the `# noqa: ML500` comment on the closing `"""` line — it suppresses all ML500 violations within that entire docstring. Per-line suppression inside docstring text is not possible (there is no `#` character on those lines). The canonical use case is referencing a name that is locked in by an external standard, such as the HTTP `Authorization` header:

```python
def authenticated_uid(credentials: ...) -> str:
    """Firebase Auth verification dependency for FastAPI.

    Extracts and verifies the Firebase ID token from the Authorization header,
    returning the authenticated user's UID.
    """  # noqa: ML500
    ...
```

## Integration with justfile and pre-commit

The recommended setup keeps the justfile as the single source of truth, with the pre-commit hook and CI both calling `just`.

**justfile:**

```just
# Run ml-lints (return types, class shape, scope, and data-trust rules)
extra-lints:
    @uv run ml-lints src/

# Include in your main lint recipe
lint:
    # ... ruff, ty, etc.
    just extra-lints
```

**`.githooks/pre-commit`** (or however your hooks are wired):

```sh
just precommit
```

**`.github/workflows/ci.yml`:**

```yaml
- run: just extra-lints
```

## Ruff integration

If you use ruff with the `RUF100` rule (unused noqa directives), tell ruff that `ML` codes belong to an external tool so it does not flag your suppression comments:

```toml
[tool.ruff.lint]
external = ["ML"]
```
