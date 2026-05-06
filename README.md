# python-lint-hooks

Custom Python linting rules, distributed as a pip-installable CLI tool.

## Rules

| Code | Description | Suggestion |
|------|-------------|------------|
| `ML001` | Function returns a bare `dict` | Use a dataclass instead |
| `ML002` | Function returns a bare `tuple` | Use a NamedTuple instead |
| `ML003` | Class defined inside a function | Move it to module level |

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
```

Exits with code `1` if any violations are found, `0` otherwise. Output follows the ruff/flake8 format:

```
src/mypackage/utils.py:42:1: ML001 Function 'parse_response' returns bare dict; use a dataclass instead
src/mypackage/models.py:17:5: ML002 Function 'as_pair' returns bare tuple; use a NamedTuple instead
```

## Configuration

Configure in `pyproject.toml` under `[tool.python-lint-hooks]`:

```toml
[tool.python-lint-hooks]
exclude = ["tests/", "migrations/", "scripts/"]
```

`exclude` is a list of directory paths (relative to the working directory). Any `.py` file under an excluded directory is skipped entirely. Paths are matched as prefixes, so `"tests/"` excludes `tests/unit/test_foo.py` as well as `tests/test_bar.py`.

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
