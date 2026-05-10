# python-lint-hooks

Custom Python linting rules, distributed as a pip-installable CLI tool.

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
| [`ML200`](docs/rules/ML200.md) | Dataclass is not frozen | Use `@dataclass(frozen=True)` |
| [`ML201`](docs/rules/ML201.md) | Class contains only forbidden types | Use a proper abstraction with well-typed fields |
| [`ML300`](docs/rules/ML300.md) | Class defined inside a function | Move it to module level |
| [`ML400`](docs/rules/ML400.md) | Unvalidated external data used without Pydantic validation | Validate with a Pydantic model before use |
| [`ML500`](docs/rules/ML500.md) | American English spelling detected | Use Australian English spelling instead |
<!-- rules-table-end -->

**ML100 - ML107** catch violations related to return types. Unlike standard linting, these rules are **recursive** and will catch bare or primitive dicts/tuples even when nested inside other types like `list[...]` or `Optional[...]`.

**The `NewType` Exception:** `ML102` and `ML107` only flag dictionaries/mappings where both the key and value are standard Python primitives (`str`, `int`, `float`, etc.). If you use a custom type (e.g. via `NewType`), the dictionary/mapping is permitted as a valid mapping.

Functions defined inside other functions are exempt from ML100-ML107 — inner definitions are implementation details and are not part of a public interface.


## Installation

Add as a dev dependency using a git source. Pin to a specific tag for reproducibility:

```toml
# pyproject.toml
[dependency-groups]
dev = [
    "python-lint-hooks",
    # ... other dev deps
]

[tool.uv.sources]
python-lint-hooks = { git = "https://github.com/lawther/python-lint-hooks", tag = "v0.1.0" }
```

During local development of the hook itself, use a path source instead:

```toml
[tool.uv.sources]
python-lint-hooks = { path = "../python-lint-hooks", editable = true }
```

Then run:

```sh
uv sync
```

## Usage

```sh
# Check a directory
uv run ml-lint src/

# Check specific files
uv run ml-lint src/mypackage/utils.py

# Check multiple directories
uv run ml-lint src/ lib/

# Use a non-default config file
uv run ml-lint src/ --config path/to/pyproject.toml

# Exclusion overrides (Ruff-style)
uv run ml-lint src/ --exclude venv/ node_modules/
uv run ml-lint src/ --extend-exclude build/
uv run ml-lint src/ --no-respect-gitignore
uv run ml-lint src/ --force-exclude

# Rule selection and ignoring
uv run ml-lint src/ --select ML100 ML200
uv run ml-lint src/ --extend-select ML300
uv run ml-lint src/ --ignore ML101
uv run ml-lint src/ --extend-ignore ML100
```

Exits with code `1` if any violations are found, `0` otherwise. Output follows the ruff/flake8 format:

```
src/mypackage/utils.py:42:1: ML100 Function 'parse_response' returns bare dict; use a dataclass instead
src/mypackage/models.py:17:5: ML103 Function 'as_pair' returns fixed-length tuple; use a NamedTuple instead
src/mypackage/models.py:10:1: ML200 Dataclass 'Config' is not frozen; use @dataclass(frozen=True)
```

## Configuration

Configure in `pyproject.toml` under `[tool.python-lint-hooks]`. Options behave similarly to [Ruff's selection settings](https://docs.astral.sh/ruff/settings/#select) and [exclusion settings](https://docs.astral.sh/ruff/settings/#exclude).

```toml
[tool.python-lint-hooks]
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
By default, `ml-lint` excludes a comprehensive list of common "junk" and environment directories, including `.git`, `.venv`, `node_modules`, `__pycache__`, `build`, `dist`, etc.

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

## Integration with justfile and pre-commit

The recommended setup keeps the justfile as the single source of truth, with the pre-commit hook and CI both calling `just`.

**justfile:**

```just
# Run ml-lint (return types, class shape, scope, and data-trust rules)
lint-ml:
    @uv run ml-lint src/

# Include in your main lint recipe
lint:
    # ... ruff, ty, etc.
    just lint-ml
```

**`.githooks/pre-commit`** (or however your hooks are wired):

```sh
just precommit
```

**`.github/workflows/ci.yml`:**

```yaml
- run: just lint-ml
```

## Ruff integration

If you use ruff with the `RUF100` rule (unused noqa directives), tell ruff that `ML` codes belong to an external tool so it does not flag your suppression comments:

```toml
[tool.ruff.lint]
external = ["ML"]
```
lint]
external = ["ML"]
```
, tell ruff that `ML` codes belong to an external tool so it does not flag your suppression comments:

```toml
[tool.ruff.lint]
external = ["ML"]
```
