# BEGIN FLEET RECIPES (CORE)
# Generated from agent_rules payload/core/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# List available recipes
default:
    @just --list

# Fail if a file, block or hook registration the fleet manages here has changed since sync
# wrote it. Reads only this repo, so it runs the same in the git hook and in CI.
check-fleet:
    @uv run --script .fleet/core/check_integrity.py

# sync writes the gate list into the next line, so it differs between repos. This repo's own
# precommit depends on it, so a check added to a family reaches the gate of every repo that
# carries the family with the next sync.
#
# Run every check the fleet requires of this repo: the integrity check and each family's gate.
precommit-fleet: check-fleet fleet-gate-core fleet-gate-rules fleet-gate-lint fleet-gate-github

# Fail if the repo's precommit skips precommit-fleet, its CI lacks uv, or its fleet.toml is invalid.
fleet-gate-core:
    @uv run --script .fleet/core/check_recipes_wired.py
    @uv run --script .fleet/core/fleet_config.py

# END FLEET RECIPES (CORE)

# The runner the shared ai_readiness recipes call; declared in agent_rules/repos.toml.
uv_run := "uv run"

# Colors and formatting
bold    := `tput bold 2>/dev/null || true`
green   := `tput setaf 2 2>/dev/null || true`
red     := `tput setaf 1 2>/dev/null || true`
reset   := `tput sgr0 2>/dev/null || true`

success := bold + green + "✔︎ "
err     := bold + red + "❌ "

# Run all lints and formatting
lint:
    @echo "Linting and formatting..."
    @uv run ruff format .
    @uv run ruff check --fix .
    @uv run ty check .
    @echo "{{success}}Lint complete{{reset}}"

# Lint this repo's own src/ and scripts/ with the working-tree ml-lints (tests/ fixtures
# deliberately violate ML500/ML501 -- excluded via [tool.ml-lints] in pyproject.toml)
extra-lints:
    @echo "Running ml-lints over its own source..."
    @uv run ml-lints src scripts
    @echo "{{success}}ml-lints self-check complete{{reset}}"

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

# Run all pre-commit checks (lint + test), auto-stage mechanical fixes
precommit: precommit-fleet
    #!/usr/bin/env bash
    if [[ "$(git config core.hooksPath 2>/dev/null)" != ".fleet/git_hooks" ]]; then
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
        just extra-lints
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

# Usage: just corpus-lint (every rule) or just corpus-lint ML701 (one rule).
# Needs .corpus.toml — see .corpus.toml.example. Developer tool, not a gate.
# Sweep rules across the external corpus looking for false positives
corpus-lint *codes:
    @{{uv_run}} scripts/corpus_lint.py {{codes}}

# Usage: just corpus-diff ML701. Answers the review-time question: what did my
# rule change add or remove? Sweeps HEAD in a temporary worktree — your working
# tree is never touched.
# Sweep the corpus twice, HEAD vs working tree, and report only what changed
corpus-diff *codes:
    @{{uv_run}} scripts/corpus_lint.py --diff {{codes}}

# BEGIN FLEET RECIPES (SCRIPTS)
# Generated from agent_rules payload/scripts/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Analyse project source files to evaluate AI agent readiness
analyse-ai-readiness *args:
    @{{uv_run}} .fleet/scripts/analyse_ai_readiness.py {{args}}

# Check source file size thresholds for AI agent readiness (fails if threshold breached)
check-ai-readiness *args:
    @{{uv_run}} .fleet/scripts/analyse_ai_readiness.py --fail-on {{args}}

# END FLEET RECIPES (SCRIPTS)

# BEGIN FLEET RECIPES (GIT_HOOKS)
# Generated from agent_rules payload/git_hooks/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Sets this repo's own local git config to prefer linear history, overriding whatever
# a clone's global config says. `pull.rebase` and `merge.ff` live in .git/config, which
# git deliberately never lets a repo commit -- so this is the one-off `setup-git-hooks`
# already asks a fresh clone to run, not something a sync can write for you. Actual
# enforcement (for a clone that skips this, or whose global config wins some other way)
# is the `pre-merge-commit` and `pre-push` hooks in .fleet/git_hooks/, which reject merge
# commits regardless of what these two settings say.
setup-linear-history:
    @git config pull.rebase true
    @git config merge.ff only
    @echo "Linear history preferences set for this clone"

# Refuses rather than clobbers. git reads exactly one hooks directory, so silently
# overwriting core.hooksPath disables whatever was there -- which is precisely how four
# repos lost their beads integration without a word (ar-x4l). `bd init` does exactly
# this, so the refusal is needed; `check-git-hooks-active` is what reports it if bd wins the
# race anyway. An unset value and the legacy `.githooks` are both safe to replace, and a value is
# judged by the directory it names, so an absolute path to either counts as that directory.
#
# Point git at .fleet/git_hooks/, so `just precommit` runs before each commit here.
setup-git-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    current=$(git config core.hooksPath || true)
    root=$(git rev-parse --show-toplevel)
    case "$current" in
        /*) named="$current" ;;
        *) named="$root/$current" ;;
    esac
    named="${named%/}"
    if [ -n "$current" ] && [ "$named" != "$root/.githooks" ] && [ "$named" != "$root/.fleet/git_hooks" ]; then
        echo "core.hooksPath is already $current -- refusing to overwrite it." >&2
        echo "git reads one hooks directory only; merge the two before setting this." >&2
        exit 1
    fi
    git config core.hooksPath .fleet/git_hooks
    echo "Git hooks set up"

# END FLEET RECIPES (GIT_HOOKS)

# BEGIN FLEET RECIPES (GITHUB)
# Generated from agent_rules payload/github/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# zizmor's version is agent_rules' locked one, stamped in by the sync, so update-deps there
# upgrades it fleet-wide. --offline keeps the audit reproducible and token-free in the git hook;
# known-vulnerable actions reach the fleet through Dependabot security updates instead. zizmor
# exits 3 when it collects no input, which is a repo with no workflows, actions or dependabot.yml.
#
# Audit this repo's GitHub Actions workflows, composite actions and dependabot.yml with zizmor.
lint-workflows:
    #!/usr/bin/env bash
    set -uo pipefail
    status=0
    uvx zizmor@1.32.0 --offline . || status=$?
    if [ "$status" -eq 3 ]; then
        echo "lint-workflows: nothing to audit"
        exit 0
    fi
    exit "$status"

# Exemptions from these checks are the repo's own, in its fleet.toml.
#
# Fail if a workflow fails zizmor, an action is not pinned to a commit SHA, or dependabot.yml can open version updates.
fleet-gate-github: lint-workflows
    @uv run --script .fleet/github/check_actions_pinned.py
    @uv run --script .fleet/github/check_dependabot_security.py

# END FLEET RECIPES (GITHUB)

# BEGIN FLEET RECIPES (RULES)
# Generated from agent_rules payload/rules/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Fail if a generated Beads integration block has reappeared in the repo's root markdown.
fleet-gate-rules:
    @uv run --script .fleet/rules/check_beads_block.py

# END FLEET RECIPES (RULES)

# BEGIN FLEET RECIPES (LINT)
# Generated from agent_rules payload/lint/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Fail if the repo's ruff config does not extend the shared one, or pyproject.toml carries a table the delivered config overrides.
fleet-gate-lint:
    @uv run --script .fleet/lint/check_lint_config.py

# END FLEET RECIPES (LINT)
