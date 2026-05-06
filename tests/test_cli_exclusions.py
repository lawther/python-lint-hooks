from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def run_lint(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "ml-lint", *args],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


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
