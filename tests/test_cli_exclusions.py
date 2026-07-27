from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import run_lint

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    # Create a dummy structure
    (tmp_path / "src").mkdir()
    # ML300: Class inside function

    (tmp_path / "src" / "main.py").write_text("def f():\n    class C: pass\n")
    (tmp_path / "src" / "helper.py").write_text("def f(): pass\n")  # Clean

    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "trash.py").write_text("def f():\n    class Trash: pass\n")

    (tmp_path / ".gitignore").write_text("ignored/\n*.log\n")

    return tmp_path


def test_default_exclude(temp_repo: Path) -> None:
    # Create a default excluded dir
    (temp_repo / "venv").mkdir()
    (temp_repo / "venv" / "lib.py").write_text("def f():\n    class Venv: pass\n")

    result = run_lint(temp_repo, ".")
    # venv/lib.py should be ignored by RUFF_DEFAULT_EXCLUDE
    # ignored/trash.py should be ignored by .gitignore
    assert "venv/lib.py" not in result.stdout
    assert "ignored/trash.py" not in result.stdout
    assert "src/main.py" in result.stdout


def test_extend_exclude(temp_repo: Path) -> None:
    result = run_lint(temp_repo, ".", "--extend-exclude", "src/main.py")
    assert "src/main.py" not in result.stdout


def test_exclude_override(temp_repo: Path) -> None:
    # --exclude should override defaults. If we exclude nothing, venv should be scanned.
    (temp_repo / "venv").mkdir(exist_ok=True)
    (temp_repo / "venv" / "lib.py").write_text("def f():\n    class Venv: pass\n")

    result = run_lint(temp_repo, ".", "--exclude", "nothing_path", "--no-respect-gitignore")
    assert "venv/lib.py" in result.stdout
    assert "ignored/trash.py" in result.stdout


def test_exclude_comma_separated(temp_repo: Path) -> None:
    # ignored/trash.py is already hidden by .gitignore; exclude src/main.py explicitly too,
    # in one comma-separated --exclude value, and confirm both are gone with no other errors.
    result = run_lint(temp_repo, ".", "--exclude", "src/main.py,ignored/")
    assert result.returncode == 0
    assert "src/main.py" not in result.stdout
    assert "ignored/trash.py" not in result.stdout


def test_path_after_exclude_flag_is_not_swallowed(temp_repo: Path) -> None:
    # Regression test: --extend-exclude used nargs="+" for its values, which greedily
    # consumed a following positional path argument, silently falling back to the
    # default "." instead of the path actually given, with no error. An explicit file
    # bypasses gitignore-based exclusion (see test_force_exclude), so if the path here
    # were swallowed and defaulting to "." kicked in instead, ignored/trash.py would stay
    # hidden by .gitignore and never appear in the output.
    result = run_lint(temp_repo, "--extend-exclude", "nonexistent/", "ignored/trash.py")
    assert "ignored/trash.py" in result.stdout


def test_respect_gitignore_toggle(temp_repo: Path) -> None:
    result_default = run_lint(temp_repo, ".")
    assert "ignored/trash.py" not in result_default.stdout

    result_no_gitignore = run_lint(temp_repo, ".", "--no-respect-gitignore")
    assert "ignored/trash.py" in result_no_gitignore.stdout


def test_force_exclude(temp_repo: Path) -> None:
    excluded_file = "ignored/trash.py"

    # By default, explicit paths are linted even if excluded
    result = run_lint(temp_repo, excluded_file)
    assert "ignored/trash.py" in result.stdout

    # With --force-exclude, it should be skipped
    result_forced = run_lint(temp_repo, excluded_file, "--force-exclude")
    assert "ignored/trash.py" not in result_forced.stdout


def test_lint_outside_cwd_uses_target_repo_root_and_gitignore(tmp_path: Path) -> None:
    # Regression test for issue #30:
    # When ml-lints is run against a path outside CWD (e.g. ../sibling_repo),
    # it must resolve gitignore and root exclusions relative to the target's containing repo.
    invoking_dir = tmp_path / "invoking_repo"
    invoking_dir.mkdir()
    (invoking_dir / ".gitignore").write_text("invoking_only.py\n")

    sibling_dir = tmp_path / "sibling_repo"
    (sibling_dir / "src").mkdir(parents=True)
    (sibling_dir / "sibling_ignored").mkdir()
    (sibling_dir / "build").mkdir()

    (sibling_dir / "src" / "valid.py").write_text("def f():\n    class ValidViolation: pass\n")
    (sibling_dir / "sibling_ignored" / "trash.py").write_text("def f():\n    class IgnoredViolation: pass\n")
    (sibling_dir / "build" / "generated.py").write_text("def f():\n    class BuiltViolation: pass\n")

    (sibling_dir / ".gitignore").write_text("sibling_ignored/\n/build/\n")

    result = run_lint(invoking_dir, "../sibling_repo")

    assert "ValidViolation" in result.stdout
    assert "IgnoredViolation" not in result.stdout
    assert "BuiltViolation" not in result.stdout


def test_subpackage_with_own_pyproject_does_not_shift_root(tmp_path: Path) -> None:
    # Regression test: a monorepo sub-package (e.g. api/pyproject.toml) sitting inside the
    # invocation directory must not be mistaken for the project root just because it carries
    # its own pyproject.toml. That previously made CLI-relative --extend-exclude patterns
    # (written relative to the invocation dir) silently match nothing.
    (tmp_path / ".git").mkdir()
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "pyproject.toml").write_text('[project]\nname = "api"\n')
    (tmp_path / "api" / "vs_secrets.py").write_text("def f():\n    class Secret: pass\n")
    (tmp_path / "api" / "other.py").write_text("def f():\n    class Other: pass\n")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "ignored.py").write_text("def f():\n    class ScriptIgnored: pass\n")
    (tmp_path / ".gitignore").write_text("scripts/ignored.py\n")

    result = run_lint(
        tmp_path,
        "api/",
        "scripts/",
        "--extend-exclude",
        "api/vs_secrets.py",
        "--config",
        "api/pyproject.toml",
    )

    assert "Other" in result.stdout
    assert "Secret" not in result.stdout
    assert "ScriptIgnored" not in result.stdout
