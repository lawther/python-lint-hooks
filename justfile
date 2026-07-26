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
    cov_json=$(mktemp)
    trap 'rm -f "$cov_json"' EXIT
    uv run pytest --cov=ml_lints --cov-report=term-missing --cov-branch --cov-report=json:"$cov_json"
    uv run python scripts/branch_summary.py "$cov_json"
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
        just docs-rules
        xargs -r -0 git add < "$staged_list"
        git add README.md
        if [ -d "docs" ]; then git add docs; fi
        just test
    ) > "$tmpfile" 2>&1
    status=$?
    if [ $status -ne 0 ]; then
        cat "$tmpfile"
        exit $status
    fi
    echo "{{success}}All pre-commit checks passed{{reset}}"

# Regenerate the rules table in README.md and individual rule docs
docs-rules:
    @uv run python scripts/generate_rules_table.py
    @uv run python scripts/generate_rule_docs.py

# [private] Fail if rule documentation is out of date (used in precommit)
check-rules-docs:
    @uv run python scripts/generate_rules_table.py --check
    @uv run python scripts/generate_rule_docs.py --check

# Scaffold a new rule. Usage: just new-rule ML150
new-rule code:
    #!/usr/bin/env bash
    set -euo pipefail
    code="{{code}}"
    lower=$(echo "$code" | tr '[:upper:]' '[:lower:]')
    rule_file="src/ml_lints/rules/${lower}.py"
    test_file="tests/rules/test_${lower}.py"
    if [ -f "$rule_file" ]; then
        echo "Rule file already exists: $rule_file" >&2
        exit 1
    fi
    sed "s/MLxxx/${code}/g" src/ml_lints/rules/_template.py | sed 's/  # ty: ignore\[unresolved-attribute\]  # placeholder replaced by just new-rule//' > "$rule_file"
    sed "s/MLxxx/${code}/g; s/mlxxx/${lower}/g" tests/rules/_template.py > "$test_file"
    python3 -c "import pathlib,sys; code=sys.argv[1]; p=pathlib.Path('src/ml_lints/violation.py'); src=p.read_text(); sentinel='    # -- add new codes above this line --'; entry='    '+code+' = \"'+code+'\"'; p.write_text(src.replace(sentinel, entry+chr(10)+sentinel))" "$code"
    echo "Created: $rule_file"
    echo "Created: $test_file"
    echo "Added:   RuleCode.${code} to src/ml_lints/violation.py"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $rule_file — fill in category/summary/suggestion and implement enter_*/leave_* hooks"
    echo "  2. Edit $test_file  — replace TODO stubs with real test cases"
    echo "  3. Run: just precommit"
    echo "  4. Run: just docs-rules  (updates README.md rules table)"

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
