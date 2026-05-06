# python-lint-hooks

Custom Python linting rules, distributed as a pip-installable CLI tool.

## Rules

| Code | Description | Suggestion |
|------|-------------|------------|
| `ML001` | Function returns a bare `dict` | Use a dataclass instead |
| `ML002` | Function returns a bare `tuple` | Use a NamedTuple instead |
| `ML003` | Class defined inside a function | Move it to module level |
| `ML005` | Dataclass is not frozen | Use `@dataclass(frozen=True)` |

**ML001 and ML002** catch all forms of bare dict/tuple returns, including unparameterised (`-> dict`), parameterised (`-> dict[str, str]`), optional (`-> dict[str, str] | None`, `-> Optional[dict[str, str]]`), union (`-> Union[dict[str, str], None]`), and `typing.Dict`/`typing.Tuple` variants.

Functions defined inside other functions are exempt from ML001/ML002 — inner functions are implementation details and are not part of a public interface.

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
```

Exits with code `1` if any violations are found, `0` otherwise. Output follows the ruff/flake8 format:

```
src/mypackage/utils.py:42:1: ML001 Function 'parse_response' returns bare dict; use a dataclass instead
src/mypackage/models.py:17:5: ML002 Function 'as_pair' returns bare tuple; use a NamedTuple instead
src/mypackage/models.py:10:1: ML005 Dataclass 'Config' is not frozen; use @dataclass(frozen=True)
```

## Configuration

Configure in `pyproject.toml` under `[tool.python-lint-hooks]`. Options behave similarly to [Ruff's exclusion settings](https://docs.astral.sh/ruff/settings/#exclude).

```toml
[tool.python-lint-hooks]
# Overwrites the default exclusion list
exclude = ["tests/", "migrations/"]

# Adds to the exclusion list without overwriting defaults
extend-exclude = ["scripts/"]

# Respect .gitignore files (default: true)
respect-gitignore = true

# Enforce exclusions even for paths passed explicitly on command line (default: false)
force-exclude = false
```

### Default Exclusions
By default, `ml-lint` excludes a comprehensive list of common "junk" and environment directories, including `.git`, `.venv`, `node_modules`, `__pycache__`, `build`, `dist`, etc.

## Suppressing individual violations

Place a `# noqa: <code>` comment on the `def` line (or on the return annotation line for multi-line signatures):

```python
# Suppress a specific code
def legacy_helper() -> dict[str, str]:  # noqa: ML001
    ...

# Suppress on the annotation line for multi-line signatures
def build_index(
    items: list[str],
) -> dict[str, int]:  # noqa: ML001
    ...

# Bare # noqa suppresses all ML codes on that line
def another() -> tuple[str, int]:  # noqa
    ...
```

## Integration with justfile and pre-commit

The recommended setup keeps the justfile as the single source of truth, with the pre-commit hook and CI both calling `just`.

**justfile:**

```just
# Check for bare dict/tuple returns and classes defined inside functions
check-bare-returns:
    @uv run ml-lint src/

# Include in your main lint recipe
lint:
    # ... ruff, ty, etc.
    just check-bare-returns
```

**`.githooks/pre-commit`** (or however your hooks are wired):

```sh
just precommit
```

**`.github/workflows/ci.yml`:**

```yaml
- run: just check-bare-returns
```

## Ruff integration

If you use ruff with the `RUF100` rule (unused noqa directives), tell ruff that `ML` codes belong to an external tool so it does not flag your suppression comments:

```toml
[tool.ruff.lint]
external = ["ML"]
```
