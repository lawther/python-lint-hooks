# Colors and formatting
bold    := `tput bold 2>/dev/null || true`
green   := `tput setaf 2 2>/dev/null || true`
red     := `tput setaf 1 2>/dev/null || true`
reset   := `tput sgr0 2>/dev/null || true`

success := bold + green + "✔︎ "
err     := bold + red + "❌ "

# List available recipes
default:
    @just --list

# Run all lints and formatting
lint:
    @echo "Linting and formatting..."
    @uv run ruff format src/ tests/
    @uv run ruff check --fix src/ tests/
    @uv run ty check src/ tests/
    @echo "{{success}}Lint complete{{reset}}"

# Run tests
test:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Running tests..."
    uv run pytest --cov=python_lint_hooks --cov-report=term-missing --cov-branch
    echo "{{success}}Tests passed{{reset}}"

# Setup the development environment from a fresh clone
setup-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    uv sync
    just setup-git-hooks
    echo "{{success}}Development environment setup complete{{reset}}"

# Install the git pre-commit hook
setup-git-hooks:
    @git config core.hooksPath .githooks
    @chmod +x .githooks/pre-commit
    @echo "{{success}}Git hooks set up{{reset}}"

# Run all pre-commit checks (lint + test), auto-stage mechanical fixes
precommit:
    #!/usr/bin/env bash
    if [[ "$(git config core.hooksPath 2>/dev/null)" != ".githooks" ]]; then
        echo "Git hooks not configured — installing now..."
        just setup-git-hooks
    fi
    echo "Running pre-commit checks..."
    tmpfile=$(mktemp)
    staged_list=$(mktemp)
    trap 'rm -f "$tmpfile" "$staged_list"' EXIT
    git diff --cached --name-only -z --diff-filter=d > "$staged_list"
    (
        set -e
        just _lint-justfile
        just _check-lock
        just lint
        xargs -r -0 git add < "$staged_list"
        just test
    ) > "$tmpfile" 2>&1
    status=$?
    if [ $status -ne 0 ]; then
        cat "$tmpfile"
        exit $status
    fi
    echo "{{success}}All pre-commit checks passed{{reset}}"

# [private] Ensure justfile recipes don't use && chains (which suppress set -e)
_lint-justfile:
    #!/usr/bin/env bash
    set -euo pipefail
    violations=$(awk '
        /^[[:space:]]+#!/ { in_shebang = 1 }
        /^[^[:space:]]/ && NF > 0 { in_shebang = 0 }
        !in_shebang && /&&/ && !/^[[:space:]]*#/ { print NR": "$0 }
    ' justfile)
    if [[ -n "$violations" ]]; then
        echo "{{err}}justfile recipes must not use && chains. Use separate lines for reliable error reporting.{{reset}}"
        echo "$violations"
        exit 1
    fi

# [private] Verify uv.lock is up to date
_check-lock:
    #!/usr/bin/env bash
    set -euo pipefail
    uv lock --check
